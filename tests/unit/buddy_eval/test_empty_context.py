"""Empty-context test: pass rule, stub and negative variants, gap cross-check, cache and traces.

The real workflow runs over an in-process MCP server built on the fixture index, with a scripted
FakeLlm. Synthetic data only.
"""

import asyncio
import io
import json
import logging
import urllib.error
import urllib.request
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator, Mapping, Sequence
from contextlib import AbstractAsyncContextManager, AbstractContextManager, asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from types import TracebackType
from typing import Any

import pytest
from fastmcp import FastMCP
from tests.unit.buddy_eval.conftest import RecordingTraceSink, golden_item, write_golden
from tests.unit.chat_bot.conftest import FakeLlm
from tests.unit.mcp_server.conftest import NOW, WEB_BASE, make_chunk

from buddy_bot.mcp_client import FastMcpConnector, McpToolError
from buddy_bot.ports import LlmUnavailableError, McpTools
from buddy_bot.schemas import AnswerDraft, BotReply, ContactExtraction, Reformulation, RetryPlan
from buddy_core.index_writer import build_index
from buddy_core.models import IndexContent
from buddy_core.store import INDEX_NAME
from buddy_eval import cli
from buddy_eval.cache import ResultCache
from buddy_eval.config import EvalSettings
from buddy_eval.empty_context import (
    EmptyContextItem,
    EmptyContextResult,
    GapCountError,
    classify,
    count_gap_documents,
    empty_scored_version,
    format_empty_context,
    run_empty_context,
    unscored,
)
from buddy_eval.fixture import build_fixture_content
from buddy_eval.golden import GoldenItem
from buddy_eval.tracing import EMPTY_SCORER_SET_VERSION, TracingError
from buddy_mcp.config import McpSettings
from buddy_mcp.gaplog import GapLog, GapRecord, InMemoryGapLog
from buddy_mcp.server import build_server
from buddy_mcp.snapshot import load_snapshot

OFF_FIXTURE = Reformulation(
    standalone_question="Domanda sintetica?",
    keywords_it=["zzzz"],
    keywords_en=["zzzz"],
    intent="question",
    sensitive_topic=None,
)
RETRY = RetryPlan(keywords_it=["yyyy"], keywords_en=["yyyy"])
MATCHING = Reformulation(
    standalone_question="Domanda sul gizmo?",
    keywords_it=["gizmo"],
    keywords_en=["gizmo"],
    intent="question",
    sensitive_topic=None,
)
GIZMO_CHUNK = make_chunk(
    "Gizmo", None, 40, 44, "gizmo handling procedure", file="Fixture/GIZMO.md", part_index=0
)
PASS_LINE = "empty_context: PASS (2/2 refused with gap)"
SKIPPED_UNSET = "gap cross-check skipped (FIRESTORE_EMULATOR_HOST unset)"


class FailingGapLog:
    """A gap log whose write always fails: the bot cannot report the gap."""

    async def record(self, gap: GapRecord) -> str:
        raise RuntimeError("firestore down")


@dataclass
class Served:
    server: FastMCP
    settings: EvalSettings
    gaplog: GapLog
    urls: list[str]

    def connector(self, url: str) -> FastMcpConnector:
        self.urls.append(url)
        return FastMcpConnector(self.server)


@pytest.fixture
def serve(tmp_path: Path, eval_settings: EvalSettings) -> Iterator[Callable[..., Served]]:
    """Factory: an in-process server over the fixture (plus optional extra chunks) and settings
    that point at the same index."""
    opened = []

    def factory(*, extra_chunks: Sequence[Any] = (), gaplog: GapLog | None = None) -> Served:
        base = build_fixture_content()
        content = IndexContent(
            handbook=base.handbook,
            chunks=(*base.chunks, *extra_chunks),
            videos={},
            source_doc_id=base.source_doc_id,
            guides_commit_sha=base.guides_commit_sha,
            pipeline_version=base.pipeline_version,
            redaction_version=base.redaction_version,
        )
        directory = tmp_path / "fixture"
        directory.mkdir(exist_ok=True)
        (directory / INDEX_NAME).unlink(missing_ok=True)
        build_index(content, directory / INDEX_NAME, now=NOW)
        snapshot = load_snapshot(directory / INDEX_NAME)
        opened.append(snapshot)
        log: GapLog = gaplog if gaplog is not None else InMemoryGapLog()
        server = build_server(
            McpSettings(
                artifact_dir=directory,
                guides_web_base=WEB_BASE,
                auth_mode="off",
                deploy_env="local",
            ),
            snapshot=snapshot,
            gaplog=log,
            now=lambda: NOW,
        )
        settings = eval_settings.model_copy(update={"fixture_dir": directory})
        return Served(server, settings, log, [])

    yield factory
    for snapshot in opened:
        snapshot.reader.close()
        snapshot.handbook_index.close()


def _items(*specs: tuple[str, str]) -> list[GoldenItem]:
    return [GoldenItem.model_validate(golden_item(item_id, kind)) for item_id, kind in specs]


def _write(
    settings: EvalSettings,
    *specs: tuple[str, str],
    overrides: Mapping[str, Mapping[str, Any]] | None = None,
) -> None:
    changes = overrides or {}
    items = [golden_item(i, k, **changes.get(i, {})) for i, k in specs]
    public = [i for i in items if i["kind"] in ("guides", "no_answer")]
    private = [i for i in items if i["kind"] not in ("guides", "no_answer")]
    write_golden(settings.golden_public_path, public)
    write_golden(settings.golden_private_path, private)


def _refusal_llm(count: int, *, reformulation: Reformulation = OFF_FIXTURE) -> FakeLlm:
    return FakeLlm({Reformulation: [reformulation] * count, RetryPlan: [RETRY] * count})


def _run(
    args: Sequence[str],
    served: Served,
    llm: FakeLlm,
    sink: RecordingTraceSink,
) -> tuple[int, str]:
    out = io.StringIO()
    code = cli.main(
        list(args),
        settings=served.settings,
        llm_factory=lambda: llm,
        connector_factory=served.connector,
        sink_factory=lambda _settings: sink,
        out=out,
    )
    return code, out.getvalue()


TWO = (("item-a", "handbook"), ("item-b", "guides"))


def test_stub_variant_every_item_is_refused_with_a_logged_gap(
    serve: Callable[..., Served],
) -> None:
    served = serve()
    _write(served.settings, *TWO)
    llm = _refusal_llm(2)
    sink = RecordingTraceSink()

    code, output = _run(["empty-context"], served, llm, sink)

    assert code == 0
    lines = output.splitlines()
    assert lines[0] == "item-a refused evidence=0 trace=http://ui/#/t/tr-1"
    assert lines[1] == "item-b refused evidence=0 trace=http://ui/#/t/tr-2"
    assert SKIPPED_UNSET in lines
    assert PASS_LINE in lines
    assert isinstance(served.gaplog, InMemoryGapLog)
    assert len(served.gaplog.records) == 2
    assert served.urls == [served.settings.mcp_empty_url] * 2
    # Text never reaches the console (T-05-29).
    assert "synthetic question" not in output
    assert "Domanda sintetica" not in output


def test_a_run_is_traced_scored_and_reported_without_text(
    serve: Callable[..., Served],
) -> None:
    served = serve()
    _write(served.settings, *TWO)
    sink = RecordingTraceSink()

    _run(["empty-context"], served, _refusal_llm(2), sink)

    assert [name for name, _ in sink.runs] == ["empty-context"]
    tags = sink.runs[0][1]
    assert tags["items"] == "2"
    assert len(tags["fixture_content_hash"]) == 64
    assert [(c.name, c.tags["item_id"], c.tags["run"]) for c in sink.traced_calls] == [
        ("bot_run", "item-a", "empty-context"),
        ("bot_run", "item-b", "empty-context"),
    ]
    assert sink.expectations["tr-1"]["expected_outcome"] == "refusal_with_gap"
    assert len(sink.score_calls) == 1
    call = sink.score_calls[0]
    assert call.scorers == "empty_context"
    assert call.trace_ids == ("tr-1", "tr-2")
    assert all(isinstance(v, EmptyContextItem) for v in call.verdicts.values())
    reports = sorted(
        (served.settings.private_dir / "eval" / "reports").glob("empty-context-*.json")
    )
    assert len(reports) == 1
    report = json.loads(reports[0].read_text(encoding="utf-8"))
    assert report["passed"] is True
    assert [i["item_id"] for i in report["items"]] == ["item-a", "item-b"]
    assert "Domanda sintetica" not in reports[0].read_text(encoding="utf-8")


def test_negative_variant_an_answer_fails_and_names_the_item(
    serve: Callable[..., Served],
) -> None:
    served = serve(extra_chunks=(GIZMO_CHUNK,))
    _write(served.settings, ("item-a", "guides"))

    async def source_url() -> str:
        async with served.connector("x").session() as tools:
            found = await tools.guides_search("gizmo")
            return found.results[0].source_url

    url = asyncio.run(source_url())
    served.urls.clear()
    llm = FakeLlm(
        {
            Reformulation: [MATCHING],
            AnswerDraft: [
                AnswerDraft(
                    answer="Procedura sintetica.", citations=[url], grounded=True, confidence=0.9
                )
            ],
        }
    )

    code, output = _run(["empty-context"], served, llm, RecordingTraceSink())

    assert code == 1
    lines = output.splitlines()
    # Two results: the keyword and the question Guides searches (05-14) both return the chunk.
    assert lines[0] == "item-a answered evidence=2 trace=http://ui/#/t/tr-1"
    assert "empty_context: FAIL (1 answered: item-a)" in lines
    assert not any(line.startswith("empty_context: PASS") for line in lines)


def test_a_smalltalk_reply_is_not_a_refusal(serve: Callable[..., Served]) -> None:
    served = serve()
    _write(served.settings, ("item-a", "handbook"))
    chitchat = OFF_FIXTURE.model_copy(update={"intent": "chitchat"})
    llm = FakeLlm({Reformulation: [chitchat]})

    code, output = _run(["empty-context"], served, llm, RecordingTraceSink())

    assert code == 1
    assert "item-a smalltalk evidence=0" in output
    assert "empty_context: FAIL (1 smalltalk: item-a)" in output.splitlines()


def test_a_refusal_whose_gap_report_failed_is_not_a_pass(serve: Callable[..., Served]) -> None:
    served = serve(gaplog=FailingGapLog())
    _write(served.settings, ("item-a", "handbook"))

    code, output = _run(["empty-context"], served, _refusal_llm(1), RecordingTraceSink())

    assert code == 1
    assert "item-a no_gap evidence=0" in output
    assert "empty_context: FAIL (1 without gap: item-a)" in output.splitlines()


def test_a_referral_with_a_logged_gap_is_a_refusal(serve: Callable[..., Served]) -> None:
    served = serve()
    _write(served.settings, ("item-a", "handbook"))
    sensitive = OFF_FIXTURE.model_copy(update={"sensitive_topic": "stipendio"})
    llm = FakeLlm({Reformulation: [sensitive], RetryPlan: [RETRY], ContactExtraction: []})

    code, output = _run(["empty-context"], served, llm, RecordingTraceSink())

    assert code == 0
    assert "item-a refused evidence=0" in output
    assert "empty_context: PASS (1/1 refused with gap)" in output.splitlines()


def test_a_llm_failure_is_incomplete_and_never_cached(
    serve: Callable[..., Served],
) -> None:
    served = serve()
    _write(served.settings, *TWO)
    llm = FakeLlm(
        {
            Reformulation: [LlmUnavailableError("down"), OFF_FIXTURE],
            RetryPlan: [RETRY],
        }
    )
    sink = RecordingTraceSink()

    code, output = _run(["empty-context"], served, llm, sink)

    assert code == 1
    assert "item-a errored" in output
    assert "item-b refused" in output
    assert "empty_context: INCOMPLETE (1 errored: item-a)" in output.splitlines()
    cached = list((served.settings.private_dir / "eval" / "cache" / "empty_context").glob("*.json"))
    assert len(cached) == 1, "only the item that completed is cached"
    # The errored item has no feedback; only the completed one is scored.
    assert sink.score_calls[0].trace_ids == ("tr-2",)


def test_a_failed_tool_call_errors_the_item(serve: Callable[..., Served]) -> None:
    served = serve()
    _write(served.settings, ("item-a", "handbook"))

    class Broken:
        def session(self) -> AbstractContextManager[McpTools]:
            raise McpToolError("search failed")

    out = io.StringIO()
    code = cli.main(
        ["empty-context"],
        settings=served.settings,
        llm_factory=lambda: _refusal_llm(1),
        connector_factory=lambda _url: Broken(),  # type: ignore[arg-type,return-value]
        sink_factory=lambda _s: RecordingTraceSink(),
        out=out,
    )

    assert code == 1
    assert "item-a errored evidence=0 trace=none" in out.getvalue()
    assert "empty_context: INCOMPLETE (1 errored: item-a)" in out.getvalue().splitlines()


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


def test_a_transport_failure_errors_the_item_and_logs_only_the_type_name(
    serve: Callable[..., Served], caplog: pytest.LogCaptureFixture
) -> None:
    served = serve()
    _write(served.settings, ("item-a", "handbook"))
    out = io.StringIO()

    with caplog.at_level(logging.WARNING, logger="buddy_eval"):
        code = cli.main(
            ["empty-context"],
            settings=served.settings,
            llm_factory=lambda: _refusal_llm(1),
            connector_factory=lambda _url: _DownConnector(),  # type: ignore[arg-type,return-value]
            sink_factory=lambda _s: RecordingTraceSink(),
            out=out,
        )

    text = out.getvalue()
    assert code == 1
    assert "item-a errored evidence=0 trace=none" in text
    # errored never passes (D-16).
    assert "empty_context: INCOMPLETE (1 errored: item-a)" in text.splitlines()
    assert "_ConnectError" in caplog.text
    assert "SENTINEL-DETAIL" not in caplog.text
    assert "SENTINEL-DETAIL" not in text


class _BrokenTraceSink(RecordingTraceSink):
    async def traced(
        self,
        name: str,
        tags: Mapping[str, str],
        fn: Callable[[], Awaitable[dict[str, Any]]],
    ) -> tuple[dict[str, Any], str]:
        raise TracingError("trace backend down")


def test_a_tracing_error_inside_the_trace_still_ends_the_run(
    serve: Callable[..., Served],
) -> None:
    served = serve()

    with pytest.raises(TracingError):
        _run_direct(served, _refusal_llm(1), _BrokenTraceSink(), _items(("item-a", "handbook")))


def test_unscored_follows_the_item_status(tmp_path: Path) -> None:
    cache = ResultCache(tmp_path / "cache")
    refused = EmptyContextItem("item-a", "refused", "refusal", True, 0, "tr-1")
    answered = EmptyContextItem("item-a", "answered", "answer", False, 2, "tr-1")
    result = EmptyContextResult((refused,), True, "gap cross-check skipped")

    cache.mark_scored("tr-1", empty_scored_version(answered))
    assert unscored(result, cache) == {"tr-1": refused}

    cache.mark_scored("tr-1", empty_scored_version(refused))
    assert unscored(result, cache) == {}
    assert empty_scored_version(refused) == f"{EMPTY_SCORER_SET_VERSION}-refused"


def test_a_failure_with_an_error_is_a_failure_not_incomplete(
    serve: Callable[..., Served],
) -> None:
    served = serve(extra_chunks=(GIZMO_CHUNK,))
    _write(served.settings, ("item-a", "guides"), ("item-b", "guides"))

    async def source_url() -> str:
        async with served.connector("x").session() as tools:
            return (await tools.guides_search("gizmo")).results[0].source_url

    url = asyncio.run(source_url())
    llm = FakeLlm(
        {
            Reformulation: [MATCHING, LlmUnavailableError("down")],
            AnswerDraft: [
                AnswerDraft(answer="Si.", citations=[url], grounded=True, confidence=0.9)
            ],
        }
    )

    code, output = _run(["empty-context"], served, llm, RecordingTraceSink())

    assert code == 1
    assert "empty_context: FAIL (1 answered: item-a; 1 errored: item-b)" in output.splitlines()


@pytest.mark.parametrize(
    "specs",
    [
        (("item-a", "no_answer"), ("item-b", "sensitive")),
        (),
    ],
)
def test_zero_approved_answerable_items_fails_and_opens_nothing(
    serve: Callable[..., Served], specs: tuple[tuple[str, str], ...]
) -> None:
    served = serve()
    _write(served.settings, *specs)
    built: list[object] = []

    def sink_factory(_settings: EvalSettings) -> RecordingTraceSink:
        built.append(1)
        return RecordingTraceSink()

    out = io.StringIO()
    code = cli.main(
        ["empty-context"],
        settings=served.settings,
        llm_factory=lambda: pytest.fail("no model call"),
        connector_factory=served.connector,
        sink_factory=sink_factory,
        out=out,
    )

    assert code == 1
    assert out.getvalue().splitlines() == ["empty_context: FAIL (no approved answerable items)"]
    assert built == []


def test_draft_and_rejected_items_are_not_run(serve: Callable[..., Served]) -> None:
    served = serve()
    _write(
        served.settings,
        ("item-a", "handbook"),
        ("item-b", "guides"),
        ("item-c", "handbook"),
        overrides={"item-b": {"review": "draft"}, "item-c": {"review": "rejected"}},
    )

    code, output = _run(["empty-context"], served, _refusal_llm(1), RecordingTraceSink())

    assert code == 0
    assert "empty_context: PASS (1/1 refused with gap)" in output.splitlines()
    assert "item-b" not in output and "item-c" not in output


def test_item_lines_and_failing_ids_are_in_ascending_id_order(
    serve: Callable[..., Served],
) -> None:
    served = serve()
    _write(served.settings, ("item-c", "handbook"), ("item-a", "guides"), ("item-b", "handbook"))
    chitchat = OFF_FIXTURE.model_copy(update={"intent": "chitchat"})
    llm = FakeLlm({Reformulation: [chitchat] * 3})

    code, output = _run(["empty-context"], served, llm, RecordingTraceSink())

    assert code == 1
    lines = output.splitlines()
    assert [line.split()[0] for line in lines[:3]] == ["item-a", "item-b", "item-c"]
    assert "empty_context: FAIL (3 smalltalk: item-a, item-b, item-c)" in lines


def test_item_option_runs_only_the_named_approved_items(serve: Callable[..., Served]) -> None:
    served = serve()
    _write(served.settings, *TWO, ("item-c", "no_answer"))

    code, output = _run(
        ["empty-context", "--item", "item-b"], served, _refusal_llm(1), RecordingTraceSink()
    )

    assert code == 0
    assert "empty_context: PASS (1/1 refused with gap)" in output.splitlines()
    assert "item-a" not in output


@pytest.mark.parametrize("requested", ["item-c", "missing"])
def test_item_option_refuses_ids_that_are_not_approved_answerable_items(
    serve: Callable[..., Served], requested: str
) -> None:
    served = serve()
    _write(served.settings, *TWO, ("item-c", "no_answer"))

    code, output = _run(
        ["empty-context", "--item", requested], served, _refusal_llm(0), RecordingTraceSink()
    )

    assert code == 1
    assert output == f"ERROR: item {requested} is not an approved handbook or guides item\n"


def test_a_missing_fixture_index_is_one_error_line_and_opens_nothing(
    serve: Callable[..., Served], tmp_path: Path
) -> None:
    served = serve()
    _write(served.settings, *TWO)
    settings = served.settings.model_copy(update={"fixture_dir": tmp_path / "nowhere"})
    built: list[object] = []
    out = io.StringIO()

    code = cli.main(
        ["empty-context"],
        settings=settings,
        llm_factory=lambda: _refusal_llm(2),
        connector_factory=served.connector,
        sink_factory=lambda _s: built.append(1) or RecordingTraceSink(),  # type: ignore[func-returns-value]
        out=out,
    )

    assert code == 1
    assert out.getvalue().startswith("ERROR: fixture index not found under FIXTURE_DIR")
    assert built == []


def test_second_run_makes_no_model_call_and_gives_the_same_verdict(
    serve: Callable[..., Served],
) -> None:
    served = serve()
    _write(served.settings, *TWO)
    llm = _refusal_llm(2)
    sink = RecordingTraceSink()
    _first_code, first = _run(["empty-context"], served, llm, sink)
    calls_after_first = len(llm.calls)

    code, second = _run(["empty-context"], served, llm, sink)

    assert code == 0
    assert len(llm.calls) == calls_after_first
    assert len(sink.traced_calls) == 2, "one traced call per fresh item"
    assert [name for name, _ in sink.runs] == ["empty-context", "empty-context"]
    assert second.splitlines()[:2] == first.splitlines()[:2]
    assert PASS_LINE in second.splitlines()
    assert "gap cross-check skipped (no fresh items)" in second.splitlines()
    # Feedback of the empty-context set is attached once per trace.
    assert len(sink.score_calls) == 2 and sink.score_calls[1].trace_ids == ()
    scored = served.settings.private_dir / "eval" / "cache" / "scored"
    assert sorted(p.name for p in scored.glob("*.json")) == [
        f"tr-1-{EMPTY_SCORER_SET_VERSION}-refused.json",
        f"tr-2-{EMPTY_SCORER_SET_VERSION}-refused.json",
    ]


def test_a_cached_item_whose_trace_is_gone_runs_again(serve: Callable[..., Served]) -> None:
    served = serve()
    _write(served.settings, ("item-a", "handbook"))
    llm = _refusal_llm(2)
    sink = RecordingTraceSink()
    _run(["empty-context"], served, llm, sink)
    sink.forget("tr-1")

    code, _output = _run(["empty-context"], served, llm, sink)

    assert code == 0
    assert len(sink.traced_calls) == 2


def test_a_change_of_the_fixture_content_is_a_cache_miss(serve: Callable[..., Served]) -> None:
    served = serve()
    _write(served.settings, ("item-a", "handbook"))
    llm = _refusal_llm(2)
    sink = RecordingTraceSink()
    _run(["empty-context"], served, llm, sink)
    changed = serve(extra_chunks=(GIZMO_CHUNK,))
    changed.settings = changed.settings.model_copy(
        update={
            "golden_public_path": served.settings.golden_public_path,
            "golden_private_path": served.settings.golden_private_path,
        }
    )

    _run(["empty-context"], changed, llm, sink)

    assert len(sink.traced_calls) == 2


def _run_direct(
    served: Served,
    llm: FakeLlm,
    sink: RecordingTraceSink,
    items: list[GoldenItem],
    **kwargs: Any,
) -> EmptyContextResult:
    return asyncio.run(
        run_empty_context(
            items,
            settings=served.settings,
            llm_factory=lambda: llm,
            connector_factory=served.connector,
            sink=sink,
            cache=ResultCache(served.settings.private_dir / "eval" / "cache"),
            **kwargs,
        )
    )


class CountSequence:
    def __init__(self, *counts: int | Exception) -> None:
        self._counts = list(counts)
        self.calls: list[tuple[str, str, str]] = []

    def __call__(self, host: str, project: str, collection: str) -> int:
        self.calls.append((host, project, collection))
        count = self._counts.pop(0)
        if isinstance(count, Exception):
            raise count
        return count


def _with_emulator(served: Served) -> None:
    served.settings = served.settings.model_copy(update={"firestore_emulator_host": "emu:8080"})


def test_gap_cross_check_passes_when_every_gap_appeared(serve: Callable[..., Served]) -> None:
    served = serve()
    _with_emulator(served)
    counter = CountSequence(0, 2)

    result = _run_direct(
        served, _refusal_llm(2), RecordingTraceSink(), _items(*TWO), count_gaps=counter
    )

    assert result.passed is True
    assert result.gap_check == "gap cross-check ok (2 documents for 2 gap_reported replies)"
    assert counter.calls == [("emu:8080", "demo-ai-buddy", "gaps_empty_context")] * 2


def test_gap_cross_check_fails_when_fewer_documents_appeared(
    serve: Callable[..., Served],
) -> None:
    served = serve()
    _with_emulator(served)

    result = _run_direct(
        served,
        _refusal_llm(2),
        RecordingTraceSink(),
        _items(*TWO),
        count_gaps=CountSequence(0, 1),
    )

    assert result.passed is False
    assert result.gap_check.startswith("gap count mismatch")
    lines = format_empty_context(result)
    assert lines[-1] == (
        "empty_context: FAIL (gap count mismatch (1 documents for 2 gap_reported replies))"
    )


def test_gap_cross_check_counts_the_delta_not_the_total(serve: Callable[..., Served]) -> None:
    served = serve()
    _with_emulator(served)

    result = _run_direct(
        served,
        _refusal_llm(2),
        RecordingTraceSink(),
        _items(*TWO),
        count_gaps=CountSequence(5, 7),
    )

    assert result.passed is True


def test_gap_cross_check_is_skipped_with_the_reason_when_the_emulator_is_unreadable(
    serve: Callable[..., Served],
) -> None:
    served = serve()
    _with_emulator(served)

    result = _run_direct(
        served,
        _refusal_llm(2),
        RecordingTraceSink(),
        _items(*TWO),
        count_gaps=CountSequence(GapCountError("URLError")),
    )

    assert result.passed is True, "gap_reported still stands when the emulator cannot be read"
    assert result.gap_check == "gap cross-check skipped (emulator unreadable: URLError)"


def test_gap_cross_check_is_skipped_when_the_emulator_goes_away_mid_run(
    serve: Callable[..., Served],
) -> None:
    served = serve()
    _with_emulator(served)

    result = _run_direct(
        served,
        _refusal_llm(2),
        RecordingTraceSink(),
        _items(*TWO),
        count_gaps=CountSequence(0, GapCountError("TimeoutError")),
    )

    assert result.passed is True
    assert result.gap_check.startswith("gap cross-check skipped (")


def test_gap_cross_check_ignores_cached_items(serve: Callable[..., Served]) -> None:
    served = serve()
    llm = _refusal_llm(2)
    sink = RecordingTraceSink()
    _run_direct(served, llm, sink, _items(*TWO))
    _with_emulator(served)
    counter = CountSequence()

    result = _run_direct(served, llm, sink, _items(*TWO), count_gaps=counter)

    assert counter.calls == [], "no fresh item, nothing to compare"
    assert result.passed is True
    assert result.gap_check == "gap cross-check skipped (no fresh items)"


def test_cross_check_counts_only_fresh_gaps(serve: Callable[..., Served]) -> None:
    served = serve()
    llm = _refusal_llm(2)
    sink = RecordingTraceSink()
    _run_direct(served, llm, sink, _items(("item-a", "handbook")))
    _with_emulator(served)

    result = _run_direct(
        served,
        llm,
        sink,
        _items(*TWO),
        count_gaps=CountSequence(1, 2),
    )

    assert result.passed is True
    assert result.gap_check == "gap cross-check ok (1 documents for 1 gap_reported replies)"


def test_items_are_paced_between_fresh_items_only(serve: Callable[..., Served]) -> None:
    served = serve()
    served.settings = served.settings.model_copy(update={"item_pause_seconds": 0.5})
    pauses: list[float] = []

    async def sleep(seconds: float) -> None:
        pauses.append(seconds)

    _run_direct(served, _refusal_llm(2), RecordingTraceSink(), _items(*TWO), sleep=sleep)

    assert pauses == [0.5]


def test_only_handbook_and_guides_items_count_as_answerable(serve: Callable[..., Served]) -> None:
    served = serve()

    result = _run_direct(
        served,
        _refusal_llm(1),
        RecordingTraceSink(),
        _items(("item-a", "no_answer"), ("item-b", "handbook"), ("item-c", "sensitive")),
    )

    assert [i.item_id for i in result.items] == ["item-b"]


@pytest.mark.parametrize(
    ("reply", "status"),
    [
        (BotReply(kind="refusal", gap_reported=True), "refused"),
        (BotReply(kind="referral", gap_reported=True), "refused"),
        (BotReply(kind="refusal"), "no_gap"),
        (BotReply(kind="referral"), "no_gap"),
        (BotReply(kind="answer", answer="x", gap_reported=True), "answered"),
        (BotReply(kind="smalltalk", gap_reported=True), "smalltalk"),
        (BotReply(kind="error"), "errored"),
    ],
)
def test_classification(reply: BotReply, status: str) -> None:
    assert classify(reply) == status


def _item(item_id: str, status: str) -> EmptyContextItem:
    return EmptyContextItem(item_id, status, "x", False, 0, None)  # type: ignore[arg-type]


def test_no_pass_line_unless_every_item_is_refused() -> None:
    for status in ("answered", "no_gap", "smalltalk", "errored"):
        result = EmptyContextResult((_item("a", "refused"), _item("b", status)), False, "x")
        assert not any(
            line.startswith("empty_context: PASS") for line in format_empty_context(result)
        )
    clean = EmptyContextResult((_item("a", "refused"),), True, "x")
    assert format_empty_context(clean)[-1] == "empty_context: PASS (1/1 refused with gap)"


def test_an_item_without_a_trace_is_printed_as_none() -> None:
    result = EmptyContextResult((_item("a", "errored"),), False, "x")

    assert format_empty_context(result)[0] == "a errored evidence=0 trace=none"


class _Response:
    def __init__(self, body: str) -> None:
        self._body = body

    def __enter__(self) -> "_Response":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        return None

    def read(self) -> bytes:
        return self._body.encode("utf-8")


def _patch_urlopen(
    monkeypatch: pytest.MonkeyPatch, bodies: Sequence[str | Exception]
) -> list[tuple[str, float]]:
    seen: list[tuple[str, float]] = []
    queue = list(bodies)

    def urlopen(url: str, timeout: float) -> _Response:
        seen.append((url, timeout))
        body = queue.pop(0)
        if isinstance(body, Exception):
            raise body
        return _Response(body)

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    return seen


def test_count_gap_documents_follows_pages_with_a_five_second_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen = _patch_urlopen(
        monkeypatch,
        [
            json.dumps({"documents": [{}, {}], "nextPageToken": "t2"}),
            json.dumps({"documents": [{}]}),
        ],
    )

    assert count_gap_documents("emu:8080", "demo-ai-buddy", "gaps_empty_context") == 3

    assert [timeout for _url, timeout in seen] == [5, 5]
    assert seen[0][0].startswith(
        "http://emu:8080/v1/projects/demo-ai-buddy/databases/(default)/documents/"
        "gaps_empty_context?"
    )
    assert "pageToken=t2" in seen[1][0]


def test_count_gap_documents_reads_an_empty_collection_as_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_urlopen(monkeypatch, ["{}"])

    assert count_gap_documents("emu:8080", "p", "c") == 0


@pytest.mark.parametrize(
    "body",
    [
        urllib.error.URLError("refused"),
        TimeoutError("slow"),
        "not json",
        "[]",
        json.dumps({"documents": "x"}),
    ],
)
def test_count_gap_documents_raises_a_gap_count_error(
    monkeypatch: pytest.MonkeyPatch, body: str | Exception
) -> None:
    _patch_urlopen(monkeypatch, [body])

    with pytest.raises(GapCountError):
        count_gap_documents("emu:8080", "p", "c")


def test_a_cached_payload_that_does_not_fit_is_a_miss(serve: Callable[..., Served]) -> None:
    served = serve()
    llm = _refusal_llm(2)
    sink = RecordingTraceSink()
    _run_direct(served, llm, sink, _items(("item-a", "handbook")))
    cached = next((served.settings.private_dir / "eval" / "cache" / "empty_context").glob("*.json"))
    cached.write_text(json.dumps({"item_id": "item-a", "status": "refused"}), encoding="utf-8")

    _run_direct(served, llm, sink, _items(("item-a", "handbook")))

    assert len(sink.traced_calls) == 2


def test_settings_defaults_name_the_fixture_server_and_collection() -> None:
    settings = EvalSettings()

    assert settings.mcp_empty_url == "http://mcp-server-empty:8000/mcp"
    assert str(settings.fixture_dir) == "/eval-empty"
    assert settings.empty_gap_collection == "gaps_empty_context"
    assert settings.firestore_emulator_host is None
    assert settings.google_cloud_project == "demo-ai-buddy"


def test_settings_read_the_emulator_host_from_the_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FIRESTORE_EMULATOR_HOST", "firestore:8080")
    monkeypatch.setenv("EMPTY_GAP_COLLECTION", "other")

    settings = EvalSettings()

    assert settings.firestore_emulator_host == "firestore:8080"
    assert settings.empty_gap_collection == "other"
