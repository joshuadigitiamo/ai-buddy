"""The full gate command: recall (informational), scoring run, empty-context, verdict and report.

Verdict cases patch the three measurements and check the composition; the readiness cases and the
warm-cache case run the real workflow over in-process MCP servers with a scripted model.
Synthetic data only.
"""

import io
import json
import logging
from collections.abc import AsyncIterator, Callable, Iterator, Sequence
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from pathlib import Path
from typing import Any

import pytest
from fastmcp import FastMCP
from tests.unit.buddy_eval.conftest import (
    GOOD_VERDICT,
    RecordingTraceSink,
    golden_item,
    write_golden,
)
from tests.unit.chat_bot.conftest import GOOD_DRAFT, REFORMULATION, FakeLlm
from tests.unit.mcp_server.conftest import NOW, WEB_BASE

from buddy_bot.mcp_client import FastMcpConnector, McpToolError
from buddy_bot.ports import LlmUnavailableError, McpConnector, McpTools
from buddy_bot.schemas import AnswerDraft, Reformulation, RetryPlan
from buddy_core.index_writer import build_index
from buddy_core.models import IndexContent
from buddy_core.store import INDEX_NAME
from buddy_eval import cli
from buddy_eval.config import EvalSettings
from buddy_eval.empty_context import EmptyContextItem, EmptyContextResult
from buddy_eval.empty_context import Status as EmptyStatus
from buddy_eval.fixture import build_fixture_content
from buddy_eval.golden import GoldenItem
from buddy_eval.judge import JudgeVerdict
from buddy_eval.recall import RecallItem, RecallResult
from buddy_eval.runner import STOP_MESSAGE, RunResult
from buddy_eval.scoring import ItemVerdict
from buddy_eval.scoring import Status as VerdictStatus
from buddy_eval.sources import IndexIdentity
from buddy_mcp.config import McpSettings
from buddy_mcp.gaplog import InMemoryGapLog
from buddy_mcp.server import build_server
from buddy_mcp.snapshot import load_snapshot

SENTINEL = "SENTINEL-QUESTION-TEXT-7f3a"
GAP_ID = "item-gap-01"
LEAVE_ID = "item-leave-01"
NOT_READY = "SKIPPED recall, run, empty_context: golden set not ready (no model call made)"
RUN_ABORTED = "SKIPPED empty_context: run stopped after consecutive errors"
NO_RESULT = Reformulation(
    standalone_question="Domanda senza risposta?",
    keywords_it=["zzzz"],
    keywords_en=["zzzz"],
    intent="question",
    sensitive_topic=None,
)
NO_RESULT_RETRY = RetryPlan(keywords_it=["yyyy"], keywords_en=["yyyy"])
IDENTITY = IndexIdentity(content_hash="c" * 64, guides_commit_sha="g" * 40, build_id="build-1")


def _public(settings: EvalSettings, *items: dict[str, Any]) -> None:
    write_golden(settings.golden_public_path, items)


def _private(settings: EvalSettings, *items: dict[str, Any]) -> None:
    write_golden(settings.golden_private_path, items)


def _both_items(settings: EvalSettings) -> None:
    _public(settings, golden_item(GAP_ID, "no_answer", question=SENTINEL))
    _private(settings, golden_item(LEAVE_ID, "handbook", question=SENTINEL + "-leave"))


class Gate:
    """Runs `cli.main(["gate"])` and counts what the command built or called."""

    def __init__(self, settings: EvalSettings, server: FastMCP, llm: FakeLlm) -> None:
        self.settings = settings
        self.llm = llm
        self.sink = RecordingTraceSink()
        self.sink_factory_calls = 0
        self.connector_calls: list[str] = []
        self.servers: dict[str, FastMCP] = {settings.mcp_url: server}

    def _sink_factory(self, _settings: EvalSettings) -> RecordingTraceSink:
        self.sink_factory_calls += 1
        return self.sink

    def _connector(self, url: str) -> McpConnector:
        self.connector_calls.append(url)
        return FastMcpConnector(self.servers[url])

    def main(self, *argv: str) -> tuple[int, str]:
        out = io.StringIO()
        code = cli.main(
            list(argv) or ["gate"],
            llm_factory=lambda: self.llm,
            sink_factory=self._sink_factory,
            settings=self.settings,
            connector_factory=self._connector,
            out=out,
        )
        return code, out.getvalue()

    @property
    def reports(self) -> list[Path]:
        return sorted((self.settings.private_dir / "eval" / "reports").glob("gate-*.json"))


@pytest.fixture
def gate(eval_settings: EvalSettings, mcp_server: FastMCP) -> Callable[[FakeLlm], Gate]:
    return lambda llm: Gate(eval_settings, mcp_server, llm)


@pytest.fixture
def empty_server(tmp_path: Path) -> Iterator[FastMCP]:
    """An in-process MCP server over the fixture index, with its own gap log."""
    base = build_fixture_content()
    content = IndexContent(
        handbook=base.handbook,
        chunks=base.chunks,
        videos={},
        source_doc_id=base.source_doc_id,
        guides_commit_sha=base.guides_commit_sha,
        pipeline_version=base.pipeline_version,
        redaction_version=base.redaction_version,
    )
    directory = tmp_path / "fixture"
    directory.mkdir()
    build_index(content, directory / INDEX_NAME, now=NOW)
    snapshot = load_snapshot(directory / INDEX_NAME)
    yield build_server(
        McpSettings(
            artifact_dir=directory, guides_web_base=WEB_BASE, auth_mode="off", deploy_env="local"
        ),
        snapshot=snapshot,
        gaplog=InMemoryGapLog(),
        now=lambda: NOW,
    )
    snapshot.reader.close()
    snapshot.handbook_index.close()


def _real_llm() -> FakeLlm:
    """Recall, the run (no_answer then handbook, one judge call) and the empty-context test."""
    return FakeLlm(
        {
            Reformulation: [REFORMULATION, NO_RESULT, REFORMULATION, NO_RESULT],
            RetryPlan: [NO_RESULT_RETRY, NO_RESULT_RETRY],
            AnswerDraft: [GOOD_DRAFT],
            JudgeVerdict: [GOOD_VERDICT],
        }
    )


# --- verdict composition over patched measurements -------------------------------------------


def _verdict(item_id: str, status: VerdictStatus, *, invented: bool | None = False) -> ItemVerdict:
    return ItemVerdict(item_id, "handbook", status, {}, (), invented, f"tr-{item_id}")


def _run_result(
    correct: int,
    *,
    wrong: int = 0,
    errored: int = 0,
    invented: int = 0,
    aborted: bool = False,
) -> RunResult:
    verdicts = [_verdict(f"item-{n:02d}", "correct") for n in range(correct)]
    verdicts += [_verdict(f"item-w{n:02d}", "wrong") for n in range(wrong)]
    verdicts += [_verdict(f"item-e{n:02d}", "errored", invented=None) for n in range(errored)]
    for position in range(invented):
        verdicts[position] = _verdict(verdicts[position].item_id, "correct", invented=True)
    return RunResult((), tuple(verdicts), aborted=aborted, identity=IDENTITY)


def _empty(*statuses: EmptyStatus, mismatch: bool = False) -> EmptyContextResult:
    items = tuple(
        EmptyContextItem(f"item-{n:02d}", s, "refusal", s == "refused", 0, f"tr-{n}")
        for n, s in enumerate(statuses)
    )
    passed = bool(items) and all(s == "refused" for s in statuses) and not mismatch
    return EmptyContextResult(items, passed, "gap cross-check skipped", mismatch)


def _recall(errored: tuple[str, ...] = ()) -> RecallResult:
    items = tuple(RecallItem(i, "handbook", False, 0.0, True, ()) for i in errored)
    return RecallResult(items, 0, 0, 0, 0, 0.0, 0.0, errored, False)


class Patched:
    """The three measurements, replaced; records which of them the gate called."""

    def __init__(self) -> None:
        self.calls: list[str] = []


@pytest.fixture
def patched(monkeypatch: pytest.MonkeyPatch) -> Callable[..., Patched]:
    def apply(
        run: RunResult, empty: EmptyContextResult | None, recall: RecallResult | None = None
    ) -> Patched:
        spy = Patched()

        async def fake_recall(items: Sequence[GoldenItem], **_: Any) -> RecallResult:
            spy.calls.append("recall")
            return recall or _recall()

        def fake_collect(items: Sequence[GoldenItem], **_: Any) -> RunResult:
            spy.calls.append("run")
            return run

        def fake_empty(items: Sequence[GoldenItem], **kw: Any) -> tuple[Any, Any]:
            spy.calls.append("empty_context")
            assert empty is not None
            return empty, kw["make_sink"]()

        monkeypatch.setattr(cli, "measure_recall", fake_recall)
        monkeypatch.setattr(cli, "_collect", fake_collect)
        monkeypatch.setattr(cli, "_run_empty_context", fake_empty)
        return spy

    return apply


def _approved(settings: EvalSettings, count: int) -> None:
    """`count` approved handbook items (private) and no draft."""
    _public(settings, golden_item(GAP_ID, "no_answer"))
    _private(settings, *(golden_item(f"item-{n:02d}", "handbook") for n in range(count - 1)))


def test_all_met_prints_pass_with_no_fail_line_and_exits_0(
    eval_settings: EvalSettings, gate: Callable[[FakeLlm], Gate], patched: Callable[..., Patched]
) -> None:
    _approved(eval_settings, 10)
    spy = patched(_run_result(9, wrong=1), _empty("refused", "refused"))

    code, text = gate(FakeLlm({})).main()

    lines = text.splitlines()
    assert code == 0
    assert [line for line in lines if line.startswith("GATE:")] == ["GATE: PASS"]
    assert lines[-1] == "GATE: PASS"
    assert not [line for line in lines if line.startswith("FAIL ")]
    assert spy.calls == ["recall", "run", "empty_context"]
    assert "recall (informational, not gating):" in lines


def test_recall_is_printed_before_the_run_and_the_run_before_empty_context(
    eval_settings: EvalSettings, gate: Callable[[FakeLlm], Gate], patched: Callable[..., Patched]
) -> None:
    _approved(eval_settings, 10)
    patched(_run_result(10), _empty("refused"))

    _, text = gate(FakeLlm({})).main()

    positions = [
        text.index("recall (informational, not gating):"),
        text.index("correctness_with_citation:"),
        text.index("empty_context: PASS"),
        text.index("GATE: PASS"),
    ]
    assert positions == sorted(positions)


def test_correctness_below_90_percent_fails_with_the_ratio(
    eval_settings: EvalSettings, gate: Callable[[FakeLlm], Gate], patched: Callable[..., Patched]
) -> None:
    _approved(eval_settings, 9)
    patched(_run_result(8, wrong=1), _empty("refused"))

    code, text = gate(FakeLlm({})).main()

    assert code == 1
    assert text.splitlines()[-2:] == [
        "GATE: FAIL",
        "FAIL correctness_with_citation: 88.9% < 90% (8/9)",
    ]


def test_exactly_90_percent_passes(
    eval_settings: EvalSettings, gate: Callable[[FakeLlm], Gate], patched: Callable[..., Patched]
) -> None:
    _approved(eval_settings, 10)
    patched(_run_result(9, wrong=1), _empty("refused"))

    code, _ = gate(FakeLlm({})).main()

    assert code == 0


def test_one_invented_policy_fails(
    eval_settings: EvalSettings, gate: Callable[[FakeLlm], Gate], patched: Callable[..., Patched]
) -> None:
    _approved(eval_settings, 10)
    patched(_run_result(10, invented=1), _empty("refused"))

    code, text = gate(FakeLlm({})).main()

    assert code == 1
    assert "FAIL invented_policies: 1 > 0" in text


def test_a_failed_empty_context_test_fails(
    eval_settings: EvalSettings, gate: Callable[[FakeLlm], Gate], patched: Callable[..., Patched]
) -> None:
    _approved(eval_settings, 10)
    patched(_run_result(10), _empty("refused", "answered"))

    code, text = gate(FakeLlm({})).main()

    assert code == 1
    assert "FAIL empty_context: failed" in text


def test_an_incomplete_empty_context_test_names_the_errored_count(
    eval_settings: EvalSettings, gate: Callable[[FakeLlm], Gate], patched: Callable[..., Patched]
) -> None:
    _approved(eval_settings, 10)
    patched(_run_result(10), _empty("refused", "errored"))

    code, text = gate(FakeLlm({})).main()

    assert code == 1
    assert "FAIL empty_context: incomplete (1 errored)" in text


def test_several_failing_metrics_are_all_named_in_the_fixed_order(
    eval_settings: EvalSettings, gate: Callable[[FakeLlm], Gate], patched: Callable[..., Patched]
) -> None:
    _approved(eval_settings, 10)
    run = _run_result(5, wrong=4, errored=1, invented=1)
    patched(run, _empty("answered"))

    code, text = gate(FakeLlm({})).main()

    fails = [line.split(":")[0] for line in text.splitlines() if line.startswith("FAIL ")]
    assert code == 1
    assert fails == [
        "FAIL errored",
        "FAIL correctness_with_citation",
        "FAIL invented_policies",
        "FAIL empty_context",
    ]


def test_an_aborted_run_skips_the_empty_context_test_and_fails_on_errors(
    eval_settings: EvalSettings, gate: Callable[[FakeLlm], Gate], patched: Callable[..., Patched]
) -> None:
    _approved(eval_settings, 10)
    spy = patched(_run_result(0, errored=3, aborted=True), None)

    code, text = gate(FakeLlm({})).main()

    lines = text.splitlines()
    assert code == 1
    assert spy.calls == ["recall", "run"]
    assert RUN_ABORTED in lines
    assert "FAIL errored: 3 items errored (incomplete run)" in lines
    assert "FAIL empty_context: not run" in lines
    assert "GATE: PASS" not in text


def test_a_partial_invented_count_of_zero_stays_unmeasured(
    eval_settings: EvalSettings, gate: Callable[[FakeLlm], Gate], patched: Callable[..., Patched]
) -> None:
    _approved(eval_settings, 10)
    patched(_run_result(0, errored=3, aborted=True), None)

    _, text = gate(FakeLlm({})).main()

    assert "FAIL invented_policies: not measured" in text.splitlines()


def test_a_partial_invented_count_above_zero_is_reported_as_counted(
    eval_settings: EvalSettings, gate: Callable[[FakeLlm], Gate], patched: Callable[..., Patched]
) -> None:
    _approved(eval_settings, 10)
    patched(_run_result(4, errored=3, invented=2, aborted=True), None)

    _, text = gate(FakeLlm({})).main()

    assert "FAIL invented_policies: 2 > 0" in text.splitlines()


def test_recall_errors_are_printed_but_never_change_the_verdict(
    eval_settings: EvalSettings, gate: Callable[[FakeLlm], Gate], patched: Callable[..., Patched]
) -> None:
    _approved(eval_settings, 10)
    patched(_run_result(10), _empty("refused"), _recall(errored=("item-00", "item-01")))

    code, text = gate(FakeLlm({})).main()

    assert code == 0
    assert "recall: INCOMPLETE (2 errored: item-00, item-01)" in text
    assert text.splitlines()[-1] == "GATE: PASS"


def test_no_approved_answerable_item_fails_the_empty_context_test(
    eval_settings: EvalSettings, gate: Callable[[FakeLlm], Gate], patched: Callable[..., Patched]
) -> None:
    _public(eval_settings, golden_item(GAP_ID, "no_answer"))
    _private(eval_settings)
    spy = patched(_run_result(1), None)

    code, text = gate(FakeLlm({})).main()

    assert code == 1
    assert "empty_context: FAIL (no approved answerable items)" in text
    assert "FAIL empty_context: failed" in text
    assert "empty_context" not in spy.calls


# --- the gate JSON report ---------------------------------------------------------------------


def test_the_json_report_holds_metrics_verdict_failing_ids_and_identity_only(
    eval_settings: EvalSettings, gate: Callable[[FakeLlm], Gate], patched: Callable[..., Patched]
) -> None:
    _both_items(eval_settings)
    patched(_run_result(0, wrong=1, errored=1, invented=0), _empty("refused", "answered"))
    harness = gate(FakeLlm({}))

    code, text = harness.main()

    assert code == 1
    assert len(harness.reports) == 1
    report = json.loads(harness.reports[0].read_text(encoding="utf-8"))
    assert f"report: {harness.reports[0]}" in text
    assert report["verdict"] == "FAIL"
    assert report["failures"][0].startswith("errored:")
    assert report["identity"] == {
        "content_hash": IDENTITY.content_hash,
        "guides_commit_sha": IDENTITY.guides_commit_sha,
        "build_id": IDENTITY.build_id,
    }
    assert report["metrics"]["approved"] == 2
    assert report["metrics"]["empty_context"] == {"passed": False, "detail": "failed"}
    assert report["failing_items"] == {
        "not_correct": ["item-w00", "item-e00"],
        "invented": [],
        "empty_context": ["item-01"],
    }
    assert SENTINEL not in harness.reports[0].read_text(encoding="utf-8")


def test_a_passing_run_writes_a_pass_report(
    eval_settings: EvalSettings, gate: Callable[[FakeLlm], Gate], patched: Callable[..., Patched]
) -> None:
    _approved(eval_settings, 10)
    patched(_run_result(10), _empty("refused"))
    harness = gate(FakeLlm({}))

    harness.main()

    report = json.loads(harness.reports[0].read_text(encoding="utf-8"))
    assert report["verdict"] == "PASS"
    assert report["failures"] == []
    assert report["metrics"]["correctness_with_citation_pct"] == 100.0


# --- readiness: no model call when the golden set cannot pass ---------------------------------


def _assert_nothing_spent(harness: Gate) -> None:
    assert harness.llm.calls == []
    assert harness.connector_calls == []
    assert harness.sink_factory_calls == 0
    assert harness.sink.traced_calls == []
    assert harness.sink.runs == []


def test_a_draft_item_fails_without_any_model_mcp_or_mlflow_call(
    eval_settings: EvalSettings, gate: Callable[[FakeLlm], Gate]
) -> None:
    _public(eval_settings, golden_item(GAP_ID, "no_answer"))
    _private(eval_settings, golden_item(LEAVE_ID, "handbook", review="draft"))
    harness = gate(_real_llm())

    code, text = harness.main()

    assert code == 1
    assert "GATE: FAIL" in text.splitlines()
    assert "FAIL golden_set: 1 draft items (golden set not fully reviewed)" in text.splitlines()
    assert NOT_READY in text.splitlines()
    assert "FAIL invented_policies: not measured" not in text
    assert "FAIL empty_context: not run" not in text
    _assert_nothing_spent(harness)


def test_a_missing_private_file_fails_without_any_call(
    eval_settings: EvalSettings, gate: Callable[[FakeLlm], Gate]
) -> None:
    _public(eval_settings, golden_item(GAP_ID, "no_answer"))
    harness = gate(_real_llm())

    code, text = harness.main()

    assert code == 1
    assert "FAIL golden_set: private handbook file missing (incomplete set)" in text.splitlines()
    assert NOT_READY in text.splitlines()
    _assert_nothing_spent(harness)


def test_no_approved_item_fails_without_any_call(
    eval_settings: EvalSettings, gate: Callable[[FakeLlm], Gate]
) -> None:
    _public(eval_settings, golden_item(GAP_ID, "no_answer", review="rejected"))
    _private(eval_settings)
    harness = gate(_real_llm())

    code, text = harness.main()

    assert code == 1
    assert "FAIL golden_set: no approved items" in text.splitlines()
    _assert_nothing_spent(harness)


def test_a_golden_load_error_is_a_golden_set_failure_without_any_call(
    eval_settings: EvalSettings, gate: Callable[[FakeLlm], Gate]
) -> None:
    _public(eval_settings, golden_item(LEAVE_ID, "no_answer"))
    _private(eval_settings, golden_item(LEAVE_ID, "handbook"))
    harness = gate(_real_llm())

    code, text = harness.main()

    lines = text.splitlines()
    assert code == 1
    assert f"FAIL golden_set: duplicate golden item id: {LEAVE_ID}" in lines
    assert lines.count("GATE: FAIL") == 1
    assert NOT_READY in lines
    _assert_nothing_spent(harness)


def test_a_missing_public_file_is_a_golden_set_failure(
    eval_settings: EvalSettings, gate: Callable[[FakeLlm], Gate]
) -> None:
    harness = gate(_real_llm())

    code, text = harness.main()

    assert code == 1
    assert "GATE: FAIL" in text.splitlines()
    assert any(line.startswith("FAIL golden_set:") for line in text.splitlines())
    _assert_nothing_spent(harness)


def test_a_not_ready_gate_still_writes_its_report(
    eval_settings: EvalSettings, gate: Callable[[FakeLlm], Gate]
) -> None:
    _public(eval_settings, golden_item(GAP_ID, "no_answer"))
    harness = gate(_real_llm())

    harness.main()

    report = json.loads(harness.reports[0].read_text(encoding="utf-8"))
    assert report["verdict"] == "FAIL"
    assert report["metrics"] is None


# --- real workflow over in-process servers ----------------------------------------------------


def _wire(harness: Gate, empty_server: FastMCP) -> None:
    harness.servers[harness.settings.mcp_empty_url] = empty_server


@pytest.fixture
def real_settings(eval_settings: EvalSettings, tmp_path: Path) -> EvalSettings:
    return eval_settings.model_copy(update={"fixture_dir": tmp_path / "fixture"})


def test_a_real_run_passes_and_a_second_run_uses_the_caches_only(
    real_settings: EvalSettings, mcp_server: FastMCP, empty_server: FastMCP
) -> None:
    _both_items(real_settings)
    llm = _real_llm()
    harness = Gate(real_settings, mcp_server, llm)
    _wire(harness, empty_server)

    first_code, first = harness.main()
    calls_after_first = len(llm.calls)
    second_code, second = harness.main()

    assert first_code == 0, first
    assert first.splitlines()[-1] == "GATE: PASS"
    assert calls_after_first > 0
    assert len(llm.calls) == calls_after_first
    assert second_code == 0
    assert second.splitlines()[-1] == "GATE: PASS"
    assert harness.connector_calls.count(real_settings.mcp_empty_url) >= 1
    assert len(harness.reports) >= 1


def test_a_missing_fixture_index_fails_the_gate_with_empty_context_not_run(
    real_settings: EvalSettings, mcp_server: FastMCP
) -> None:
    _both_items(real_settings)
    llm = FakeLlm(
        {
            Reformulation: [REFORMULATION, NO_RESULT, REFORMULATION],
            RetryPlan: [NO_RESULT_RETRY],
            AnswerDraft: [GOOD_DRAFT],
            JudgeVerdict: [GOOD_VERDICT],
        }
    )
    harness = Gate(real_settings, mcp_server, llm)

    code, text = harness.main()

    lines = text.splitlines()
    assert code == 1
    assert any(line.startswith("ERROR: fixture index not found") for line in lines)
    assert "FAIL empty_context: not run" in lines
    assert lines.count("GATE: FAIL") == 1


def test_an_unavailable_model_errors_the_item_and_the_gate_fails(
    real_settings: EvalSettings, mcp_server: FastMCP, empty_server: FastMCP
) -> None:
    _both_items(real_settings)
    llm = FakeLlm(
        {
            Reformulation: [REFORMULATION, NO_RESULT, REFORMULATION, NO_RESULT],
            RetryPlan: [NO_RESULT_RETRY, NO_RESULT_RETRY],
            AnswerDraft: [LlmUnavailableError("down")],
        }
    )
    harness = Gate(real_settings, mcp_server, llm)
    _wire(harness, empty_server)

    code, text = harness.main()

    assert code == 1
    assert "FAIL errored: 1 items errored (incomplete run)" in text.splitlines()


class _ConnectError(Exception):
    """An httpx-style transport error: neither OSError nor McpToolError."""


class _DownConnector:
    """An MCP connector whose session never opens (server unreachable or restarting)."""

    def session(self) -> AbstractAsyncContextManager[McpTools]:
        return self._session()

    @asynccontextmanager
    async def _session(self) -> AsyncIterator[McpTools]:
        raise _ConnectError("connect failed SENTINEL-DETAIL")
        yield  # pragma: no cover


def test_an_mcp_outage_errors_items_stops_the_run_and_still_reports_a_fail(
    real_settings: EvalSettings,
    mcp_server: FastMCP,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    settings = real_settings.model_copy(update={"max_consecutive_errors": 2})
    _both_items(settings)
    llm = FakeLlm({Reformulation: [REFORMULATION] * 6, RetryPlan: [NO_RESULT_RETRY] * 6})
    harness = Gate(settings, mcp_server, llm)

    def down(url: str) -> McpConnector:
        harness.connector_calls.append(url)
        return _DownConnector()

    harness._connector = down  # type: ignore[method-assign]

    with caplog.at_level(logging.INFO, logger="buddy_eval"):
        code, text = harness.main()

    lines = text.splitlines()
    captured = capsys.readouterr()
    assert code == 1
    assert STOP_MESSAGE.format(n=2) in lines
    assert "FAIL errored: 2 items errored (incomplete run)" in lines
    assert RUN_ABORTED in lines
    assert lines.count("GATE: FAIL") == 1
    assert len(harness.reports) == 1
    assert "Traceback" not in text + captured.err
    assert "item item-gap-01 errored: _ConnectError" in caplog.text
    assert "SENTINEL-DETAIL" not in text + captured.out + captured.err + caplog.text


@pytest.mark.parametrize("error", [McpToolError("tool down"), LlmUnavailableError("down")])
def test_an_mcp_or_llm_error_reaching_main_is_one_error_line_and_exit_1(
    eval_settings: EvalSettings, mcp_server: FastMCP, error: Exception
) -> None:
    _both_items(eval_settings)

    def broken_sink(_settings: EvalSettings) -> RecordingTraceSink:
        raise error

    out = io.StringIO()
    code = cli.main(
        ["run"],
        settings=eval_settings,
        llm_factory=lambda: FakeLlm({}),
        connector_factory=lambda _url: FastMcpConnector(mcp_server),
        sink_factory=broken_sink,
        out=out,
    )

    assert code == 1
    assert out.getvalue().splitlines() == [f"ERROR: {type(error).__name__}: {error}"]


# --- privacy ----------------------------------------------------------------------------------


def test_question_text_never_reaches_stdout_stderr_or_logs(
    real_settings: EvalSettings,
    mcp_server: FastMCP,
    empty_server: FastMCP,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    _both_items(real_settings)
    harness = Gate(real_settings, mcp_server, _real_llm())
    _wire(harness, empty_server)

    with caplog.at_level(logging.DEBUG):
        _, text = harness.main()

    captured = capsys.readouterr()
    for stream in (text, captured.out, captured.err, caplog.text):
        assert SENTINEL not in stream
    assert any(SENTINEL in call.user for call in harness.llm.calls)
    for path in harness.reports:
        assert SENTINEL not in path.read_text(encoding="utf-8")
