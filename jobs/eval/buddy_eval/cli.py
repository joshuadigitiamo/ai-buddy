"""Command line of the evaluation job: ``run``, ``gate``, ``lint``, ``recall``, ``build-fixture``
and ``empty-context``.

Collaborators that talk to the outside world (the model client, the MCP connector, the trace
sink) are injected, so the same entry point runs in-process in tests and, from 05-04, with the
production adapters. Output is limited to item ids, kinds, statuses, counts and trace links;
question, answer and evidence text are never printed or logged (D-04, D-06, BOT-11 posture).
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Final, TextIO

from pydantic import ValidationError

from buddy_bot.llm import build_llm_client
from buddy_bot.mcp_client import FastMcpConnector
from buddy_bot.ports import LlmClient, McpConnector
from buddy_eval.cache import ResultCache, bot_version
from buddy_eval.config import EvalSettings
from buddy_eval.empty_context import (
    RUN_NAME as EMPTY_RUN_NAME,
)
from buddy_eval.empty_context import (
    EmptyContextResult,
    format_empty_context,
    run_empty_context,
    unscored,
)
from buddy_eval.empty_context import payload as empty_payload
from buddy_eval.fixture import FixtureError, build_fixture
from buddy_eval.gate import GateInputs, GateVerdict, evaluate, format_verdict
from buddy_eval.golden import (
    GoldenError,
    GoldenItem,
    GoldenSet,
    format_lint,
    lint_golden,
    load_golden,
)
from buddy_eval.recall import (
    RecallResult,
    default_connector_factory,
    format_recall,
    measure_recall,
)
from buddy_eval.recall import payload as recall_payload
from buddy_eval.report import emit, write_json_report
from buddy_eval.runner import RunResult, run_items
from buddy_eval.scoring import headline
from buddy_eval.sources import SourceIndex
from buddy_eval.tracing import EMPTY_SCORER_SET_VERSION, MlflowTraceSink, TraceSink, TracingError

LOGGER_NAME: Final = "buddy_eval"
LOG_FORMAT: Final = "%(levelname)s %(name)s %(message)s"
_VALUE_ERROR_PREFIX: Final = "Value error, "

# Failures that end a command with one ERROR line and exit code 1.
_EXPECTED_ERRORS: Final = (GoldenError, TracingError, FixtureError, OSError)

LlmFactory = Callable[[], LlmClient]
SinkFactory = Callable[[EvalSettings], TraceSink]
ConnectorFactory = Callable[[str], McpConnector]


class _FixtureMissing(Exception):
    """The empty-context fixture index does not exist under FIXTURE_DIR."""


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="buddy_eval", description="AI Buddy evaluation job")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="run approved golden items through the bot and score them")
    run.add_argument("--item", action="append", default=[], metavar="ID", help="only this item")
    sub.add_parser("gate", help="run every approved item and print the milestone gate verdict")
    sub.add_parser("lint", help="check the golden set against the schema, the index and privacy")
    recall = sub.add_parser("recall", help="measure Recall@5 of handbook and Guides search")
    recall.add_argument("--item", action="append", default=[], metavar="ID", help="only this item")
    empty = sub.add_parser(
        "empty-context", help="every approved answerable item must be refused over a fixture index"
    )
    empty.add_argument("--item", action="append", default=[], metavar="ID", help="only this item")
    fixture = sub.add_parser(
        "build-fixture", help="build the empty-context fixture index from its committed sources"
    )
    fixture.add_argument(
        "--dest", required=True, type=Path, help="directory that receives index.db"
    )
    return parser


def _describe_validation_error(exc: ValidationError) -> str:
    """Name the offending variables and our own rule messages; error inputs may be secrets."""
    parts: set[str] = set()
    for err in exc.errors():
        if err["loc"]:
            parts.add(str(err["loc"][0]).upper())
        else:
            parts.add(str(err["msg"]).removeprefix(_VALUE_ERROR_PREFIX))
    return "invalid settings: " + "; ".join(sorted(parts) or ["(unknown)"])


def _build_fixture(dest: Path, out: TextIO) -> int:
    """Build the fixture index; no settings, model, MCP or MLflow use."""
    try:
        meta = build_fixture(dest)
    except (FixtureError, OSError) as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=out)
        return 1
    print(f"fixture built: build_id={meta.build_id} content_hash={meta.content_hash}", file=out)
    return 0


def _select(golden: GoldenSet, requested: Sequence[str]) -> tuple[GoldenItem, ...] | str:
    """The approved items to run, or the id of the first requested item that is not approved."""
    approved = {item.id: item for item in golden.approved()}
    for item_id in requested:
        if item_id not in approved:
            return item_id
    if not requested:
        return golden.approved()
    return tuple(approved[item_id] for item_id in sorted(set(requested)))


def _collect(
    items: Sequence[GoldenItem],
    *,
    settings: EvalSettings,
    llm_factory: LlmFactory,
    connector_factory: ConnectorFactory,
    sink: TraceSink,
) -> RunResult:
    return asyncio.run(
        run_items(
            items,
            settings=settings,
            llm_factory=llm_factory,
            connector_factory=connector_factory,
            sink=sink,
        )
    )


def _lint(settings: EvalSettings, out: TextIO) -> int:
    """No model, MCP or MLflow use: files and the index only."""
    try:
        golden = load_golden(settings.golden_public_path, settings.golden_private_path)
    except GoldenError as exc:
        print(f"error: golden_set: {exc}", file=out)
        print("lint: 1 errors", file=out)
        return 1
    paths = (settings.golden_public_path, settings.golden_private_path)
    raw_texts = {p.name: p.read_text(encoding="utf-8") for p in paths if p.is_file()}
    index = SourceIndex.open(settings.artifact_dir)
    issues = lint_golden(golden, index, raw_texts=raw_texts)
    for line in format_lint(golden, issues):
        print(line, file=out)
    return 1 if any(issue.severity == "error" for issue in issues) else 0


def _recall_items(golden: GoldenSet, requested: Sequence[str]) -> tuple[GoldenItem, ...] | str:
    """Approved handbook and Guides items, or the id of the first requested item that is not."""
    searchable = {i.id: i for i in golden.approved() if i.kind in ("handbook", "guides")}
    for item_id in requested:
        if item_id not in searchable:
            return item_id
    if not requested:
        return tuple(searchable.values())
    return tuple(searchable[item_id] for item_id in sorted(set(requested)))


def _recall(
    args: argparse.Namespace,
    *,
    settings: EvalSettings,
    llm_factory: LlmFactory,
    connector_factory: ConnectorFactory,
    out: TextIO,
) -> int:
    golden = load_golden(settings.golden_public_path, settings.golden_private_path)
    selected = _recall_items(golden, args.item)
    if isinstance(selected, str):
        print(f"ERROR: item {selected} is not an approved handbook or guides item", file=out)
        return 1
    if not selected:
        print("no approved handbook or guides items", file=out)
        return 1
    result = asyncio.run(
        measure_recall(
            selected,
            settings=settings,
            llm_factory=llm_factory,
            connector_factory=connector_factory,
            cache=ResultCache(settings.private_dir / "eval" / "cache"),
        )
    )
    for line in format_recall(result):
        print(line, file=out)
    # Retrieved ids are private page ids: the per-item file stays under PRIVATE_DIR.
    path = write_json_report(
        settings.private_dir / "eval" / "reports", "recall", recall_payload(result)
    )
    print(f"report: {path}", file=out)
    return 1 if result.errored_ids else 0


def _run_empty_context(
    selected: Sequence[GoldenItem],
    *,
    settings: EvalSettings,
    llm_factory: LlmFactory,
    connector_factory: ConnectorFactory,
    make_sink: Callable[[], TraceSink],
) -> tuple[EmptyContextResult, TraceSink]:
    """One traced and scored empty-context run over the fixture server.

    Raises _FixtureMissing, before `make_sink` is called, when the fixture index is missing.
    """
    try:
        identity = SourceIndex.open(settings.fixture_dir).identity
    except FileNotFoundError as exc:
        raise _FixtureMissing(str(settings.fixture_dir)) from exc
    cache = ResultCache(settings.private_dir / "eval" / "cache")
    sink = make_sink()
    tags = {
        "items": str(len(selected)),
        "fixture_content_hash": identity.content_hash,
        "fixture_build_id": identity.build_id,
        "bot_version": bot_version(),
        "reformulate_model": settings.reformulate_model,
        "answer_model": settings.answer_model,
    }
    with sink.run(EMPTY_RUN_NAME, tags):
        result = asyncio.run(
            run_empty_context(
                selected,
                settings=settings,
                llm_factory=llm_factory,
                connector_factory=connector_factory,
                sink=sink,
                cache=cache,
            )
        )
        fresh = unscored(result, cache)
        sink.score(list(fresh), fresh, scorers="empty_context")
        for trace_id in fresh:
            cache.mark_scored(trace_id, EMPTY_SCORER_SET_VERSION)
    return result, sink


def _empty_context(
    args: argparse.Namespace,
    *,
    settings: EvalSettings,
    llm_factory: LlmFactory,
    connector_factory: ConnectorFactory,
    sink_factory: SinkFactory,
    out: TextIO,
) -> int:
    """Real bot over the fixture server; PASS only when every item is refused with a gap."""
    golden = load_golden(settings.golden_public_path, settings.golden_private_path)
    selected = _recall_items(golden, args.item)
    if isinstance(selected, str):
        print(f"ERROR: item {selected} is not an approved handbook or guides item", file=out)
        return 1
    if not selected:
        # Nothing to test is a failure, never a pass; no index or MLflow run is opened.
        for line in format_empty_context(EmptyContextResult((), False, "")):
            print(line, file=out)
        return 1
    try:
        result, sink = _run_empty_context(
            selected,
            settings=settings,
            llm_factory=llm_factory,
            connector_factory=connector_factory,
            make_sink=lambda: sink_factory(settings),
        )
    except _FixtureMissing as exc:
        print(f"ERROR: fixture index not found under FIXTURE_DIR ({exc})", file=out)
        return 1
    for line in format_empty_context(result, trace_url=sink.trace_url):
        print(line, file=out)
    path = write_json_report(
        settings.private_dir / "eval" / "reports", EMPTY_RUN_NAME, empty_payload(result)
    )
    print(f"report: {path}", file=out)
    return 0 if result.passed else 1


SKIPPED_NOT_READY: Final = (
    "SKIPPED recall, run, empty_context: golden set not ready (no model call made)"
)
SKIPPED_EMPTY_CONTEXT: Final = "SKIPPED empty_context: run stopped after consecutive errors"
_GOLDEN_SET_PREFIX: Final = "golden_set:"
_EMPTY_FAILED: Final = ("answered", "smalltalk", "no_gap")


def _invented_count(result: RunResult, golden: GoldenSet) -> int | None:
    """Items flagged with an invented policy, or None when the count cannot be trusted.

    The count is complete only when every approved item has a judged verdict. A partial count
    that already found a flagged item is reported as it is (the gate fails on it either way);
    a partial count of zero says nothing, so it stays unmeasured (carry-forward from 05-08).
    """
    summary = headline(result.verdicts)
    complete = (
        len(result.verdicts) == len(golden.approved())
        and summary.errored == 0
        and summary.unjudged == 0
    )
    if complete or summary.invented > 0:
        return summary.invented
    return None


def _empty_context_detail(result: EmptyContextResult) -> str:
    errored = len(result.ids_with("errored"))
    hard_failure = result.gap_mismatch or any(result.ids_with(s) for s in _EMPTY_FAILED)
    if errored and not hard_failure:
        return f"incomplete ({errored} errored)"
    return "failed"


def _gate_inputs(
    result: RunResult, golden: GoldenSet, empty: EmptyContextResult | None
) -> GateInputs:
    summary = headline(result.verdicts)
    return GateInputs(
        approved_total=len(golden.approved()),
        correct=summary.correct,
        unjudged=summary.unjudged,
        errored=summary.errored,
        drafts=len(golden.drafts()),
        private_file_present=golden.private_file_present,
        invented=_invented_count(result, golden),
        empty_context_passed=None if empty is None else empty.passed,
        empty_context_detail=None if empty is None else _empty_context_detail(empty),
    )


def _gate_payload(
    verdict: GateVerdict,
    *,
    result: RunResult | None,
    golden: GoldenSet | None,
    inputs: GateInputs | None,
    recall: RecallResult | None,
    empty: EmptyContextResult | None,
) -> dict[str, object]:
    """The private gate report: numbers, the verdict, failing item ids and the index identity."""
    payload: dict[str, object] = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "verdict": "PASS" if verdict.passed else "FAIL",
        "failures": list(verdict.failures),
        "identity": None,
        "metrics": None,
        "failing_items": None,
    }
    if result is None or golden is None or inputs is None:
        return payload
    identity = result.identity
    if identity is not None:
        payload["identity"] = {
            "content_hash": identity.content_hash,
            "guides_commit_sha": identity.guides_commit_sha,
            "build_id": identity.build_id,
        }
    approved = inputs.approved_total
    payload["metrics"] = {
        "approved": approved,
        "correct": inputs.correct,
        "unjudged": inputs.unjudged,
        "errored": inputs.errored,
        "correctness_with_citation_pct": inputs.correct * 100 / approved if approved else None,
        "invented_policies": inputs.invented,
        "empty_context": {
            "passed": inputs.empty_context_passed,
            "detail": inputs.empty_context_detail,
        },
        "recall": None
        if recall is None
        else {
            "handbook": [recall.handbook_hits, recall.handbook_total],
            "guides": [recall.guides_hits, recall.guides_total],
            "errored": list(recall.errored_ids),
        },
    }
    payload["failing_items"] = {
        "not_correct": [v.item_id for v in result.verdicts if v.status != "correct"],
        "invented": [v.item_id for v in result.verdicts if v.invented is True],
        "empty_context": []
        if empty is None
        else [i.item_id for i in empty.items if i.status != "refused"],
    }
    return payload


def _finish_gate(
    verdict: GateVerdict, settings: EvalSettings, payload: dict[str, object], out: TextIO
) -> int:
    """Write the report first, so a failed write never leaves a printed verdict behind."""
    path = write_json_report(settings.private_dir / "eval" / "reports", "gate", payload)
    print(f"report: {path}", file=out)
    for line in format_verdict(verdict):
        print(line, file=out)
    return 0 if verdict.passed else 1


def _gate_not_ready(
    failures: Sequence[str], settings: EvalSettings, golden: GoldenSet | None, out: TextIO
) -> int:
    """FAIL on the golden set alone: no model, MCP or MLflow use (D-14 budget)."""
    verdict = GateVerdict(passed=False, failures=tuple(failures))
    print(SKIPPED_NOT_READY, file=out)
    return _finish_gate(
        verdict,
        settings,
        _gate_payload(verdict, result=None, golden=golden, inputs=None, recall=None, empty=None),
        out,
    )


def _gate(
    *,
    settings: EvalSettings,
    llm_factory: LlmFactory,
    sink_factory: SinkFactory,
    connector_factory: ConnectorFactory | None,
    out: TextIO,
) -> int:
    """Recall (informational), the scoring run and the empty-context test, then one verdict."""
    try:
        golden = load_golden(settings.golden_public_path, settings.golden_private_path)
    except GoldenError as exc:
        return _gate_not_ready([f"{_GOLDEN_SET_PREFIX} {exc}"], settings, None, out)
    readiness = evaluate(
        GateInputs(
            approved_total=len(golden.approved()),
            correct=0,
            unjudged=0,
            errored=0,
            drafts=len(golden.drafts()),
            private_file_present=golden.private_file_present,
            invented=None,
            empty_context_passed=None,
        )
    )
    not_ready = [f for f in readiness.failures if f.startswith(_GOLDEN_SET_PREFIX)]
    if not_ready:
        return _gate_not_ready(not_ready, settings, golden, out)

    run_connector = connector_factory or FastMcpConnector
    answerable = tuple(i for i in golden.approved() if i.kind in ("handbook", "guides"))
    recall = asyncio.run(
        measure_recall(
            answerable,
            settings=settings,
            llm_factory=llm_factory,
            # The measurement needs the top five results of both tools, not the bot's limits.
            connector_factory=connector_factory or default_connector_factory,
            cache=ResultCache(settings.private_dir / "eval" / "cache"),
        )
    )
    print("recall (informational, not gating):", file=out)
    for line in format_recall(recall):
        print(line, file=out)

    sink = sink_factory(settings)
    result = _collect(
        golden.approved(),
        settings=settings,
        llm_factory=llm_factory,
        connector_factory=run_connector,
        sink=sink,
    )
    emit(result, settings=settings, sink=sink, out=out)

    empty: EmptyContextResult | None = None
    if result.aborted:
        print(SKIPPED_EMPTY_CONTEXT, file=out)
    elif not answerable:
        # Nothing to test is a failure, never a pass; no index or MLflow run is opened.
        empty = EmptyContextResult((), False, "")
        for line in format_empty_context(empty):
            print(line, file=out)
    else:
        try:
            empty, _ = _run_empty_context(
                answerable,
                settings=settings,
                llm_factory=llm_factory,
                connector_factory=run_connector,
                make_sink=lambda: sink,
            )
        except _FixtureMissing as exc:
            print(f"ERROR: fixture index not found under FIXTURE_DIR ({exc})", file=out)
        else:
            for line in format_empty_context(empty, trace_url=sink.trace_url):
                print(line, file=out)

    inputs = _gate_inputs(result, golden, empty)
    verdict = evaluate(inputs)
    payload = _gate_payload(
        verdict, result=result, golden=golden, inputs=inputs, recall=recall, empty=empty
    )
    return _finish_gate(verdict, settings, payload, out)


def _execute(
    args: argparse.Namespace,
    *,
    settings: EvalSettings,
    llm_factory: LlmFactory,
    sink_factory: SinkFactory,
    connector_factory: ConnectorFactory | None,
    out: TextIO,
) -> int:
    if args.command == "lint":
        return _lint(settings, out)
    if args.command == "recall":
        return _recall(
            args,
            settings=settings,
            llm_factory=llm_factory,
            # The measurement needs the top five results of both tools, not the bot's limits.
            connector_factory=connector_factory or default_connector_factory,
            out=out,
        )
    run_connector = connector_factory or FastMcpConnector
    if args.command == "empty-context":
        return _empty_context(
            args,
            settings=settings,
            llm_factory=llm_factory,
            connector_factory=run_connector,
            sink_factory=sink_factory,
            out=out,
        )
    if args.command == "gate":
        return _gate(
            settings=settings,
            llm_factory=llm_factory,
            sink_factory=sink_factory,
            connector_factory=connector_factory,
            out=out,
        )
    golden = load_golden(settings.golden_public_path, settings.golden_private_path)
    selected = _select(golden, args.item)
    if isinstance(selected, str):
        print(f"ERROR: item {selected} is not an approved item", file=out)
        return 1
    if not selected:
        # Nothing to run: no sink is built, so no MLflow run opens (EVAL-05 empty edge).
        print("no approved items", file=out)
        return 1
    sink = sink_factory(settings)
    result = _collect(
        selected,
        settings=settings,
        llm_factory=llm_factory,
        connector_factory=run_connector,
        sink=sink,
    )
    emit(result, settings=settings, sink=sink, out=out)
    summary = headline(result.verdicts)
    return 1 if result.aborted or summary.errored else 0


def main(
    argv: Sequence[str] | None = None,
    *,
    settings: EvalSettings | None = None,
    llm_factory: LlmFactory | None = None,
    connector_factory: ConnectorFactory | None = None,
    sink_factory: SinkFactory | None = None,
    out: TextIO | None = None,
) -> int:
    """Run one subcommand; return 0 on success or PASS, 1 on a reported failure or FAIL, 2 on
    bad arguments."""
    try:
        args = _build_parser().parse_args(argv)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 1

    stream = out if out is not None else sys.stdout
    logger = logging.getLogger(LOGGER_NAME)
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter(LOG_FORMAT))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    try:
        if args.command == "build-fixture":
            return _build_fixture(args.dest, stream)
        resolved = settings if settings is not None else EvalSettings()
        return _execute(
            args,
            settings=resolved,
            # Production defaults (D-13): the real model client, MCP connector and MLflow sink.
            llm_factory=llm_factory or (lambda: build_llm_client(resolved)),
            sink_factory=sink_factory or MlflowTraceSink,
            connector_factory=connector_factory,
            out=stream,
        )
    except ValidationError as exc:
        print(f"ERROR: {_describe_validation_error(exc)}", file=stream)
        return 1
    except _EXPECTED_ERRORS as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=stream)
        return 1
    finally:
        logger.removeHandler(handler)
