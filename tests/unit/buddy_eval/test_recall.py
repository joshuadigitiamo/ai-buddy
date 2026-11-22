"""Recall@5 per source: hit math, the D5 trigger, errors, the reformulation cache.

Fake search tools answer by query; one test runs the real in-process MCP server. Synthetic data
only.
"""

import asyncio
import io
import json
import logging
from collections.abc import AsyncIterator, Mapping, Sequence
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from pathlib import Path
from typing import Any, Literal

import pytest
from fastmcp import FastMCP
from tests.unit.buddy_eval.conftest import golden_item, write_golden
from tests.unit.chat_bot.conftest import REFORMULATION, FakeLlm
from tests.unit.mcp_server.conftest import MAPPED

from buddy_bot.mcp_client import FastMcpConnector, McpToolError
from buddy_bot.ports import LlmUnavailableError, McpTools
from buddy_bot.prompts import build_reformulate_system
from buddy_bot.schemas import Reformulation
from buddy_core.escalation import load_escalation_table
from buddy_eval import cli, recall
from buddy_eval.cache import ResultCache
from buddy_eval.config import EvalSettings
from buddy_eval.golden import GoldenItem
from buddy_eval.recall import RecallResult, format_recall, measure_recall
from buddy_mcp.models import (
    GapReportOutput,
    GuidesSearchOutput,
    GuidesSectionResult,
    HandbookPageResult,
    HandbookSearchOutput,
)

SENTINEL = "SENTINEL-QUESTION-TEXT"
SECTION = MAPPED.chunk_key.rsplit("/", 1)[0]
D5_LINE = "D5 TRIGGER: guides recall@5 < 0.8 -> plan the hybrid dense+BM25 upgrade (RET-01)"

Script = Mapping[str, "Sequence[str] | Exception"]


def _handbook_output(urls: Sequence[str]) -> HandbookSearchOutput:
    return HandbookSearchOutput(
        status="ok" if urls else "no_results",
        query="q",
        results=[
            HandbookPageResult(
                page_id=url.removeprefix("handbook://"),
                title="t",
                text="synthetic",
                source_url=url,
                revision_date="2026-01-01",
            )
            for url in urls
        ],
    )


def _guides_output(section_ids: Sequence[str]) -> GuidesSearchOutput:
    return GuidesSearchOutput(
        status="ok" if section_ids else "no_results",
        query="q",
        results=[
            GuidesSectionResult(
                section_id=section_id,
                file="a.md",
                heading="h",
                line_start=1,
                line_end=2,
                text="synthetic",
                source_url=f"https://example.invalid/{section_id}",
                revision_date="2026-01-01",
            )
            for section_id in section_ids
        ],
    )


class FakeTools:
    """Answers each search by query; an exception entry is raised."""

    def __init__(self, handbook: Script | None = None, guides: Script | None = None) -> None:
        self._handbook = handbook or {}
        self._guides = guides or {}
        self.queries: list[tuple[str, str]] = []

    async def handbook_search(self, query: str) -> HandbookSearchOutput:
        self.queries.append(("handbook", query))
        found = self._handbook.get(query, [])
        if isinstance(found, Exception):
            raise found
        return _handbook_output(found)

    async def guides_search(self, query: str) -> GuidesSearchOutput:
        self.queries.append(("guides", query))
        found = self._guides.get(query, [])
        if isinstance(found, Exception):
            raise found
        return _guides_output(found)

    async def report_gap(self, question: str, tried: Sequence[str]) -> GapReportOutput:
        raise AssertionError("recall never reports a gap")


class FakeConnector:
    def __init__(self, tools: McpTools) -> None:
        self._tools = tools
        self.sessions = 0

    def session(self) -> AbstractAsyncContextManager[McpTools]:
        return self._session()

    @asynccontextmanager
    async def _session(self) -> AsyncIterator[McpTools]:
        self.sessions += 1
        yield self._tools


def _ref(
    n: int, intent: Literal["question", "chitchat", "off_topic"] = "question"
) -> Reformulation:
    return Reformulation(
        standalone_question="synthetic",
        keywords_it=[f"it{n}"],
        keywords_en=[f"en{n}"],
        intent=intent,
    )


def _guides_items(count: int, **overrides: Any) -> list[GoldenItem]:
    return [
        GoldenItem.model_validate(
            golden_item(
                f"gd-{n:02d}",
                "guides",
                question=f"{SENTINEL} guides {n}",
                expected_sources=[f"a.md#h2/s{n}"],
                **overrides,
            )
        )
        for n in range(count)
    ]


def _handbook_items(count: int, sources: Sequence[Sequence[str]] | None = None) -> list[GoldenItem]:
    return [
        GoldenItem.model_validate(
            golden_item(
                f"hb-{n:02d}",
                "handbook",
                question=f"{SENTINEL} handbook {n}",
                expected_sources=list(sources[n]) if sources else [f"handbook://page-{n}"],
            )
        )
        for n in range(count)
    ]


def _guides_script(hits: Sequence[bool]) -> Script:
    """Item n returns its own section when hit, else an unrelated one."""
    return {f"en{n}": [f"a.md#h2/s{n}/0" if h else "other.md#x/0"] for n, h in enumerate(hits)}


@pytest.fixture
def cache(tmp_path: Path) -> ResultCache:
    return ResultCache(tmp_path / "cache")


def _measure(
    items: Sequence[GoldenItem],
    settings: EvalSettings,
    connector: FakeConnector,
    cache: ResultCache,
    llm: FakeLlm | None = None,
    sleeps: list[float] | None = None,
) -> RecallResult:
    fake = llm or FakeLlm({Reformulation: [_ref(n) for n in range(len(items))]})

    async def sleep(seconds: float) -> None:
        if sleeps is not None:
            sleeps.append(seconds)

    return asyncio.run(
        measure_recall(
            items,
            settings=settings,
            llm_factory=lambda: fake,
            connector_factory=lambda _url: connector,
            cache=cache,
            sleep=sleep,
        )
    )


class TestRecallMath:
    def test_four_of_five_guides_items_is_point_eight_and_no_trigger(
        self, eval_settings: EvalSettings, cache: ResultCache
    ) -> None:
        tools = FakeTools(guides=_guides_script([True, True, True, True, False]))

        result = _measure(_guides_items(5), eval_settings, FakeConnector(tools), cache)

        assert (result.guides_hits, result.guides_total) == (4, 5)
        assert result.trigger is False
        lines = format_recall(result)
        assert "recall@5 guides: 0.80 (4/5; fractional 0.80)" in lines
        assert D5_LINE not in lines

    def test_three_of_four_guides_items_is_point_seventy_five_and_the_trigger(
        self, eval_settings: EvalSettings, cache: ResultCache
    ) -> None:
        tools = FakeTools(guides=_guides_script([True, True, True, False]))

        result = _measure(_guides_items(4), eval_settings, FakeConnector(tools), cache)

        assert result.trigger is True
        lines = format_recall(result)
        assert "recall@5 guides: 0.75 (3/4; fractional 0.75)" in lines
        assert D5_LINE in lines

    def test_zero_guides_items_is_not_applicable_and_warns(
        self, eval_settings: EvalSettings, cache: ResultCache
    ) -> None:
        tools = FakeTools(handbook={"it0": ["handbook://page-0"]})

        result = _measure(_handbook_items(1), eval_settings, FakeConnector(tools), cache)

        assert result.trigger is False
        lines = format_recall(result)
        assert "recall@5 guides: n/a (0 items)" in lines
        assert "recall@5 handbook: 1.00 (1/1; fractional 1.00)" in lines
        assert any(line.startswith("warning:") and "D5 trigger" in line for line in lines)
        assert D5_LINE not in lines

    def test_an_item_with_two_expected_sources_and_one_retrieved_is_half_a_hit(
        self, eval_settings: EvalSettings, cache: ResultCache
    ) -> None:
        items = _handbook_items(1, [["handbook://page-a", "handbook://page-b"]])
        tools = FakeTools(handbook={"it0": ["handbook://page-a", "handbook://zzz"]})

        result = _measure(items, eval_settings, FakeConnector(tools), cache)

        assert result.items[0].hit is True
        assert result.items[0].fraction == 0.5
        assert result.handbook_fraction == 0.5
        assert "recall@5 handbook: 1.00 (1/1; fractional 0.50)" in format_recall(result)

    def test_two_results_matching_one_expected_section_count_once(
        self, eval_settings: EvalSettings, cache: ResultCache
    ) -> None:
        tools = FakeTools(guides={"en0": ["a.md#h2/s0/0", "a.md#h2/s0/1", "a.md#h2/s0/2"]})

        result = _measure(_guides_items(1), eval_settings, FakeConnector(tools), cache)

        assert result.items[0].fraction == 1.0
        assert result.guides_fraction == 1.0

    def test_a_section_sharing_only_a_name_prefix_is_not_a_match(
        self, eval_settings: EvalSettings, cache: ResultCache
    ) -> None:
        tools = FakeTools(guides={"en0": ["a.md#h2/s00/0"]})

        result = _measure(_guides_items(1), eval_settings, FakeConnector(tools), cache)

        assert result.items[0].hit is False

    def test_only_the_first_five_results_count_in_tool_order(
        self, eval_settings: EvalSettings, cache: ResultCache
    ) -> None:
        filler = [f"other.md#x/{n}" for n in range(5)]
        tools = FakeTools(
            guides={"en0": [*filler, "a.md#h2/s0/0"], "en1": [*filler[:4], "a.md#h2/s1/0"]}
        )

        result = _measure(_guides_items(2), eval_settings, FakeConnector(tools), cache)

        assert [i.hit for i in result.items] == [False, True]
        assert all(len(i.retrieved) <= 5 for i in result.items)

    def test_an_empty_result_list_is_a_miss_not_an_error(
        self, eval_settings: EvalSettings, cache: ResultCache
    ) -> None:
        result = _measure(_guides_items(1), eval_settings, FakeConnector(FakeTools()), cache)

        assert result.items[0].hit is False
        assert result.items[0].errored is False
        assert result.errored_ids == ()
        assert result.guides_total == 1

    def test_the_intent_information_line_counts_non_question_reformulations(
        self, eval_settings: EvalSettings, cache: ResultCache
    ) -> None:
        llm = FakeLlm({Reformulation: [_ref(0, "chitchat"), _ref(1)]})
        tools = FakeTools(guides=_guides_script([True, True]))

        result = _measure(_guides_items(2), eval_settings, FakeConnector(tools), cache, llm)

        assert "info: 1 items reformulated as chitchat or off_topic (search still ran)" in (
            format_recall(result)
        )
        assert result.guides_hits == 2


class TestErrors:
    def test_a_tool_error_errors_the_item_and_marks_the_run_incomplete(
        self, eval_settings: EvalSettings, cache: ResultCache
    ) -> None:
        failing = McpToolError("guides_search failed")
        guides: Script = {**_guides_script([True, True]), "en0": failing}

        result = _measure(
            _guides_items(2), eval_settings, FakeConnector(FakeTools(guides=guides)), cache
        )

        assert result.errored_ids == ("gd-00",)
        assert (result.guides_hits, result.guides_total) == (1, 1)
        assert "recall: INCOMPLETE (1 errored: gd-00)" in format_recall(result)

    def test_a_reformulation_error_errors_the_item_and_is_not_cached(
        self, eval_settings: EvalSettings, cache: ResultCache
    ) -> None:
        items = _guides_items(1)
        failing = FakeLlm({Reformulation: [LlmUnavailableError("down")]})
        tools = FakeTools(guides=_guides_script([True]))

        first = _measure(items, eval_settings, FakeConnector(tools), cache, failing)
        second = _measure(items, eval_settings, FakeConnector(tools), cache)

        assert first.errored_ids == ("gd-00",)
        assert first.guides_total == 0
        assert second.errored_ids == ()
        assert second.guides_hits == 1

    def test_the_all_errored_source_is_not_applicable_not_zero(
        self, eval_settings: EvalSettings, cache: ResultCache
    ) -> None:
        tools = FakeTools(guides={"en0": McpToolError("guides_search failed")})

        result = _measure(_guides_items(1), eval_settings, FakeConnector(tools), cache)

        lines = format_recall(result)
        assert "recall@5 guides: n/a (0 measured)" in lines
        assert result.trigger is False


class _ConnectError(Exception):
    """An httpx-style transport error: neither OSError nor McpToolError."""


class _FailingConnector(FakeConnector):
    """A session that fails to open, or that fails on close after yielding the tools."""

    def __init__(self, tools: McpTools, *, on_enter: bool) -> None:
        super().__init__(tools)
        self._on_enter = on_enter

    @asynccontextmanager
    async def _session(self) -> AsyncIterator[McpTools]:
        self.sessions += 1
        if self._on_enter:
            raise _ConnectError("connect failed SENTINEL-DETAIL")
        yield self._tools
        raise _ConnectError("close failed SENTINEL-DETAIL")


class TestSessionFailure:
    def test_a_session_that_fails_to_open_errors_every_item_and_raises_nothing(
        self,
        eval_settings: EvalSettings,
        cache: ResultCache,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        connector = _FailingConnector(FakeTools(guides=_guides_script([True, True])), on_enter=True)

        with caplog.at_level(logging.WARNING, logger="buddy_eval"):
            result = _measure(_guides_items(2), eval_settings, connector, cache)

        assert result.errored_ids == ("gd-00", "gd-01")
        assert result.guides_total == 0
        assert "recall: INCOMPLETE (2 errored: gd-00, gd-01)" in format_recall(result)
        assert "_ConnectError" in caplog.text
        assert "SENTINEL-DETAIL" not in caplog.text

    def test_a_transport_error_mid_run_keeps_measured_items_and_errors_the_rest(
        self, eval_settings: EvalSettings, cache: ResultCache
    ) -> None:
        guides: Script = {**_guides_script([True, False, True]), "en1": _ConnectError("gone")}

        result = _measure(
            _guides_items(3), eval_settings, FakeConnector(FakeTools(guides=guides)), cache
        )

        assert result.errored_ids == ("gd-01", "gd-02")
        assert (result.guides_hits, result.guides_total) == (1, 1)
        assert "recall: INCOMPLETE (2 errored: gd-01, gd-02)" in format_recall(result)

    def test_a_session_that_fails_on_close_keeps_every_measured_item(
        self, eval_settings: EvalSettings, cache: ResultCache
    ) -> None:
        connector = _FailingConnector(
            FakeTools(guides=_guides_script([True, False])), on_enter=False
        )

        result = _measure(_guides_items(2), eval_settings, connector, cache)

        assert result.errored_ids == ()
        assert (result.guides_hits, result.guides_total) == (1, 2)


class TestCacheAndSession:
    def test_a_second_run_makes_no_model_call_and_gives_the_same_numbers(
        self, eval_settings: EvalSettings, cache: ResultCache
    ) -> None:
        items = _guides_items(4)
        tools = FakeTools(guides=_guides_script([True, True, True, False]))
        first_llm = FakeLlm({Reformulation: [_ref(n) for n in range(4)]})
        first = _measure(items, eval_settings, FakeConnector(tools), cache, first_llm)
        second_llm = FakeLlm({})

        second = _measure(items, eval_settings, FakeConnector(tools), cache, second_llm)

        assert len(first_llm.calls) == 4
        assert second_llm.calls == []
        assert format_recall(second) == format_recall(first)

    def test_a_changed_reformulate_model_is_a_cache_miss(
        self, eval_settings: EvalSettings, cache: ResultCache
    ) -> None:
        items = _guides_items(1)
        tools = FakeTools(guides=_guides_script([True]))
        _measure(items, eval_settings, FakeConnector(tools), cache)
        other = eval_settings.model_copy(update={"reformulate_model": "another-haiku"})
        llm = FakeLlm({Reformulation: [_ref(0)]})

        _measure(items, other, FakeConnector(tools), cache, llm)

        assert len(llm.calls) == 1

    def test_the_cached_reformulation_is_keyed_by_the_question_text(
        self, eval_settings: EvalSettings, cache: ResultCache
    ) -> None:
        tools = FakeTools(guides=_guides_script([True, True]))
        _measure(_guides_items(1), eval_settings, FakeConnector(tools), cache)
        other = [
            GoldenItem.model_validate(
                golden_item(
                    "gd-00",
                    "guides",
                    question="a different question",
                    expected_sources=["a.md#h2/s0"],
                )
            )
        ]
        llm = FakeLlm({Reformulation: [_ref(0)]})

        _measure(other, eval_settings, FakeConnector(tools), cache, llm)

        assert len(llm.calls) == 1

    def test_the_reformulate_node_is_called_with_the_bot_prompt_and_an_empty_history(
        self, eval_settings: EvalSettings, cache: ResultCache
    ) -> None:
        llm = FakeLlm({Reformulation: [_ref(0)]})
        tools = FakeTools(guides=_guides_script([True]))

        _measure(_guides_items(1), eval_settings, FakeConnector(tools), cache, llm)

        call = llm.calls[0]
        assert call.model == eval_settings.reformulate_model
        assert call.user == f"{SENTINEL} guides 0"
        assert call.system == build_reformulate_system(load_escalation_table())

    def test_no_answer_and_sensitive_items_are_never_queried_or_reformulated(
        self, eval_settings: EvalSettings, cache: ResultCache
    ) -> None:
        refusals = [
            GoldenItem.model_validate(golden_item("na-00", "no_answer")),
            GoldenItem.model_validate(golden_item("se-00", "sensitive")),
        ]
        llm = FakeLlm({Reformulation: [_ref(0)]})
        tools = FakeTools(guides=_guides_script([True]))

        result = _measure(
            [*refusals, *_guides_items(1)], eval_settings, FakeConnector(tools), cache, llm
        )

        assert [i.item_id for i in result.items] == ["gd-00"]
        assert len(llm.calls) == 1
        assert tools.queries == [("guides", "en0")]

    def test_one_session_serves_all_items_and_each_search_uses_its_own_keywords(
        self, eval_settings: EvalSettings, cache: ResultCache
    ) -> None:
        items = [*_guides_items(2), *_handbook_items(1)]
        connector = FakeConnector(FakeTools(guides=_guides_script([True, True])))

        _measure(items, eval_settings, connector, cache)

        assert connector.sessions == 1
        tools = connector._tools
        assert isinstance(tools, FakeTools)
        assert tools.queries == [("guides", "en0"), ("guides", "en1"), ("handbook", "it2")]

    def test_the_pause_is_paced_between_items_only(
        self, eval_settings: EvalSettings, cache: ResultCache
    ) -> None:
        settings = eval_settings.model_copy(update={"item_pause_seconds": 0.25})
        sleeps: list[float] = []
        tools = FakeTools(guides=_guides_script([True, True, True]))

        _measure(_guides_items(3), settings, FakeConnector(tools), cache, sleeps=sleeps)

        assert sleeps == [0.25, 0.25]

    def test_nothing_to_measure_opens_no_session(
        self, eval_settings: EvalSettings, cache: ResultCache
    ) -> None:
        connector = FakeConnector(FakeTools())

        result = _measure([], eval_settings, connector, cache)

        assert connector.sessions == 0
        assert result.items == ()

    def test_logs_never_contain_question_text(
        self,
        eval_settings: EvalSettings,
        cache: ResultCache,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        tools = FakeTools(
            guides={**_guides_script([True, True]), "en0": McpToolError("guides_search failed")}
        )
        caplog.set_level(logging.INFO, logger="buddy_eval")

        result = _measure(_guides_items(2), eval_settings, FakeConnector(tools), cache)

        assert SENTINEL not in caplog.text
        assert SENTINEL not in "\n".join(format_recall(result))
        assert "gd-00" in caplog.text


def test_the_default_connector_asks_for_the_top_five_of_both_tools(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: dict[str, object] = {}

    class _Recorder:
        def __init__(self, target: str, **kwargs: int) -> None:
            seen["target"] = target
            seen.update(kwargs)

    monkeypatch.setattr(recall, "FastMcpConnector", _Recorder)

    recall.default_connector_factory("http://mcp.invalid/mcp")

    assert seen == {"target": "http://mcp.invalid/mcp", "handbook_limit": 5, "guides_limit": 5}


class TestRecallCommand:
    def _write(
        self,
        settings: EvalSettings,
        public: Sequence[dict[str, Any]],
        private: Sequence[dict[str, Any]],
    ) -> None:
        write_golden(settings.golden_public_path, public)
        write_golden(settings.golden_private_path, private)

    def _real_items(self) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        public = [
            golden_item("gd-real", "guides", question=f"{SENTINEL} g", expected_sources=[SECTION]),
            golden_item("na-real", "no_answer", question=f"{SENTINEL} n"),
            golden_item(
                "gd-draft",
                "guides",
                review="draft",
                question=f"{SENTINEL} d",
                expected_sources=[SECTION],
            ),
        ]
        private = [
            golden_item(
                "hb-real",
                "handbook",
                question=f"{SENTINEL} h",
                expected_sources=["handbook://02-ferie"],
            )
        ]
        return public, private

    def test_the_command_measures_both_sources_over_the_real_server_and_writes_a_private_report(
        self,
        eval_settings: EvalSettings,
        mcp_server: FastMCP,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        self._write(eval_settings, *self._real_items())
        monkeypatch.setattr(cli, "MlflowTraceSink", lambda _s: pytest.fail("sink built"))
        llm = FakeLlm({Reformulation: [REFORMULATION, REFORMULATION]})
        out = io.StringIO()

        code = cli.main(
            ["recall"],
            settings=eval_settings,
            llm_factory=lambda: llm,
            connector_factory=lambda _url: FastMcpConnector(
                mcp_server, handbook_limit=5, guides_limit=5
            ),
            out=out,
        )

        lines = out.getvalue().splitlines()
        assert code == 0
        assert "recall@5 handbook: 1.00 (1/1; fractional 1.00)" in lines
        assert "recall@5 guides: 1.00 (1/1; fractional 1.00)" in lines
        assert SENTINEL not in out.getvalue()
        reports = list((eval_settings.private_dir / "eval" / "reports").glob("recall-*.json"))
        assert len(reports) == 1
        report = json.loads(reports[0].read_text(encoding="utf-8"))
        assert [i["id"] for i in report["items"]] == ["gd-real", "hb-real"]
        assert any(r.startswith("handbook://") for i in report["items"] for r in i["retrieved"])
        assert f"report: {reports[0]}" in lines

    def test_an_errored_item_exits_one_with_the_incomplete_line(
        self, eval_settings: EvalSettings
    ) -> None:
        self._write(eval_settings, *self._real_items())
        tools = FakeTools(guides={"en0": McpToolError("guides_search failed")})
        out = io.StringIO()

        code = cli.main(
            ["recall", "--item", "gd-real"],
            settings=eval_settings,
            llm_factory=lambda: FakeLlm({Reformulation: [_ref(0)]}),
            connector_factory=lambda _url: FakeConnector(tools),
            out=out,
        )

        assert code == 1
        assert "recall: INCOMPLETE (1 errored: gd-real)" in out.getvalue()

    @pytest.mark.parametrize("item_id", ["gd-draft", "na-real", "nope-00"])
    def test_only_approved_handbook_or_guides_items_can_be_requested(
        self, eval_settings: EvalSettings, item_id: str
    ) -> None:
        self._write(eval_settings, *self._real_items())
        out = io.StringIO()

        code = cli.main(
            ["recall", "--item", item_id],
            settings=eval_settings,
            llm_factory=lambda: pytest.fail("llm built"),
            connector_factory=lambda _url: pytest.fail("connector built"),
            out=out,
        )

        assert code == 1
        assert (
            out.getvalue() == f"ERROR: item {item_id} is not an approved handbook or guides item\n"
        )

    def test_no_approved_searchable_items_is_a_reported_failure(
        self, eval_settings: EvalSettings
    ) -> None:
        self._write(eval_settings, [golden_item("na-real", "no_answer")], [])
        out = io.StringIO()

        code = cli.main(["recall"], settings=eval_settings, out=out)

        assert code == 1
        assert out.getvalue() == "no approved handbook or guides items\n"

    def test_the_production_default_is_the_top_five_connector_not_the_bot_limits(
        self, eval_settings: EvalSettings, mcp_server: FastMCP, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        public, private = self._real_items()
        self._write(eval_settings, public, private)
        built: list[str] = []

        def top_five(url: str) -> FastMcpConnector:
            built.append(url)
            return FastMcpConnector(mcp_server, handbook_limit=5, guides_limit=5)

        monkeypatch.setattr(cli, "default_connector_factory", top_five)
        monkeypatch.setattr(cli, "FastMcpConnector", lambda _url: pytest.fail("run connector used"))
        out = io.StringIO()

        code = cli.main(
            ["recall"],
            settings=eval_settings,
            llm_factory=lambda: FakeLlm({Reformulation: [REFORMULATION, REFORMULATION]}),
            out=out,
        )

        assert code == 0
        assert built == [eval_settings.mcp_url]
