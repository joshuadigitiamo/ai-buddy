"""Command line of the evaluation job: ``run``, ``gate`` and ``lint``.

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
from typing import Final, TextIO

from pydantic import ValidationError

from buddy_bot.llm import build_llm_client
from buddy_bot.mcp_client import FastMcpConnector
from buddy_bot.ports import LlmClient, McpConnector
from buddy_eval.config import EvalSettings
from buddy_eval.gate import GateInputs, evaluate, format_verdict
from buddy_eval.golden import (
    GoldenError,
    GoldenItem,
    GoldenSet,
    format_lint,
    lint_golden,
    load_golden,
)
from buddy_eval.report import emit
from buddy_eval.runner import RunResult, run_items
from buddy_eval.scoring import headline
from buddy_eval.sources import SourceIndex
from buddy_eval.tracing import MlflowTraceSink, TraceSink, TracingError

LOGGER_NAME: Final = "buddy_eval"
LOG_FORMAT: Final = "%(levelname)s %(name)s %(message)s"
_VALUE_ERROR_PREFIX: Final = "Value error, "

# Failures that end a command with one ERROR line and exit code 1.
_EXPECTED_ERRORS: Final = (GoldenError, TracingError, OSError)

LlmFactory = Callable[[], LlmClient]
SinkFactory = Callable[[EvalSettings], TraceSink]
ConnectorFactory = Callable[[str], McpConnector]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="buddy_eval", description="AI Buddy evaluation job")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="run approved golden items through the bot and score them")
    run.add_argument("--item", action="append", default=[], metavar="ID", help="only this item")
    sub.add_parser("gate", help="run every approved item and print the milestone gate verdict")
    sub.add_parser("lint", help="check the golden set against the schema, the index and privacy")
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


def _gate_inputs(result: RunResult, golden: GoldenSet) -> GateInputs:
    summary = headline(result.verdicts)
    return GateInputs(
        approved_total=len(golden.approved()),
        correct=summary.correct,
        unjudged=summary.unjudged,
        errored=summary.errored,
        drafts=len(golden.drafts()),
        private_file_present=golden.private_file_present,
        invented=None,
        empty_context_passed=None,
    )


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
    run_connector = connector_factory or FastMcpConnector
    golden = load_golden(settings.golden_public_path, settings.golden_private_path)
    gate = args.command == "gate"
    selected = _select(golden, [] if gate else args.item)
    if isinstance(selected, str):
        print(f"ERROR: item {selected} is not an approved item", file=out)
        return 1
    if not selected:
        # Nothing to run: no sink is built, so no MLflow run opens (EVAL-05 empty edge).
        if gate:
            verdict = evaluate(_gate_inputs(RunResult((), (), aborted=False), golden))
            for line in format_verdict(verdict):
                print(line, file=out)
        else:
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
    if gate:
        verdict = evaluate(_gate_inputs(result, golden))
        for line in format_verdict(verdict):
            print(line, file=out)
        return 0 if verdict.passed else 1
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
