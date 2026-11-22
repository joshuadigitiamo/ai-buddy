"""Error states of the collect loop: consecutive-error stop, errored is never wrong, no retries.

In-process only: scripted model, the in-process MCP server and a recording trace sink.
Synthetic data only.
"""

import asyncio
import io

import pytest
from fastmcp import FastMCP
from tests.unit.buddy_eval.conftest import RecordingTraceSink, golden_item, write_golden
from tests.unit.chat_bot.conftest import GOOD_DRAFT, REFORMULATION, FakeLlm

from buddy_bot.mcp_client import FastMcpConnector
from buddy_bot.ports import LlmError, LlmUnavailableError
from buddy_bot.schemas import AnswerDraft, Reformulation
from buddy_eval import cli
from buddy_eval.config import EvalSettings
from buddy_eval.golden import GoldenItem, load_golden
from buddy_eval.report import emit
from buddy_eval.runner import STOP_MESSAGE, RunResult, run_items

IDS = ("item-aa-01", "item-bb-01", "item-cc-01", "item-dd-01", "item-ee-01")
STOP_LINE = "stopped after 3 consecutive errors; re-run the same command to resume"


def _write_items(settings: EvalSettings, ids: tuple[str, ...]) -> None:
    write_golden(
        settings.golden_public_path, [golden_item("item-rej-01", "no_answer", review="rejected")]
    )
    write_golden(settings.golden_private_path, [golden_item(i, "handbook") for i in ids])


def _items(settings: EvalSettings, ids: tuple[str, ...]) -> tuple[GoldenItem, ...]:
    _write_items(settings, ids)
    return load_golden(settings.golden_public_path, settings.golden_private_path).approved()


def _collect(
    settings: EvalSettings,
    server: FastMCP,
    llm: FakeLlm,
    sink: RecordingTraceSink,
    ids: tuple[str, ...],
) -> RunResult:
    return asyncio.run(
        run_items(
            _items(settings, ids),
            settings=settings,
            llm_factory=lambda: llm,
            connector_factory=lambda _url: FastMcpConnector(server),
            sink=sink,
        )
    )


def _unavailable(count: int) -> list[AnswerDraft | Exception]:
    return [LlmUnavailableError("unavailable") for _ in range(count)]


def _calls(llm: FakeLlm, schema: type) -> int:
    return sum(1 for call in llm.calls if call.schema is schema)


def test_the_run_stops_after_the_limit_and_later_items_get_no_llm_call(
    eval_settings: EvalSettings, mcp_server: FastMCP
) -> None:
    llm = FakeLlm({Reformulation: [REFORMULATION] * 5, AnswerDraft: _unavailable(5)})
    sink = RecordingTraceSink()

    result = _collect(eval_settings, mcp_server, llm, sink, IDS)

    assert result.aborted is True
    assert [o.item_id for o in result.outcomes] == list(IDS[:3])
    assert {o.status for o in result.outcomes} == {"errored"}
    assert [v.item_id for v in result.verdicts] == list(IDS[:3])
    assert _calls(llm, Reformulation) == 3
    assert _calls(llm, AnswerDraft) == 3
    assert len(sink.runs) == 1
    assert sink.score_calls[0].trace_ids == ()


def test_emit_prints_the_stop_message_after_the_item_lines(
    eval_settings: EvalSettings, mcp_server: FastMCP
) -> None:
    llm = FakeLlm({Reformulation: [REFORMULATION] * 5, AnswerDraft: _unavailable(5)})
    sink = RecordingTraceSink()
    result = _collect(eval_settings, mcp_server, llm, sink, IDS)
    out = io.StringIO()

    emit(result, settings=eval_settings, sink=sink, out=out)

    lines = out.getvalue().splitlines()
    assert STOP_MESSAGE.format(n=3) == STOP_LINE
    assert lines[-1] == STOP_LINE
    assert lines[0] == f"{IDS[0]} handbook errored trace=none error=LlmUnavailableError"
    assert not any(IDS[3] in line or IDS[4] in line for line in lines)


def test_a_complete_run_does_not_print_the_stop_message(
    eval_settings: EvalSettings, mcp_server: FastMCP
) -> None:
    llm = FakeLlm({Reformulation: [REFORMULATION], AnswerDraft: [GOOD_DRAFT]})
    sink = RecordingTraceSink()
    result = _collect(eval_settings, mcp_server, llm, sink, IDS[:1])
    out = io.StringIO()

    emit(result, settings=eval_settings, sink=sink, out=out)

    assert result.aborted is False
    assert "consecutive errors" not in out.getvalue()


def test_an_errored_item_between_good_ones_resets_the_counter(
    eval_settings: EvalSettings, mcp_server: FastMCP
) -> None:
    # error, error, good, error, error: never three in a row, so no stop.
    llm = FakeLlm(
        {
            Reformulation: [REFORMULATION] * 5,
            AnswerDraft: [
                LlmUnavailableError("x"),
                LlmUnavailableError("x"),
                GOOD_DRAFT,
                LlmUnavailableError("x"),
                LlmUnavailableError("x"),
            ],
        }
    )

    result = _collect(eval_settings, mcp_server, llm, RecordingTraceSink(), IDS)

    assert result.aborted is False
    assert [o.status for o in result.outcomes] == [
        "errored",
        "errored",
        "completed",
        "errored",
        "errored",
    ]
    assert _calls(llm, AnswerDraft) == 5


def test_errored_items_are_errored_never_wrong(
    eval_settings: EvalSettings, mcp_server: FastMCP
) -> None:
    llm = FakeLlm(
        {Reformulation: [REFORMULATION] * 2, AnswerDraft: [LlmUnavailableError("x"), GOOD_DRAFT]}
    )

    result = _collect(eval_settings, mcp_server, llm, RecordingTraceSink(), IDS[:2])

    assert [v.status for v in result.verdicts] == ["errored", "unjudged"]
    assert "wrong" not in {v.status for v in result.verdicts}


def test_an_error_reply_from_a_failed_reformulation_is_errored(
    eval_settings: EvalSettings, mcp_server: FastMCP
) -> None:
    llm = FakeLlm({Reformulation: [LlmError("down")]})

    result = _collect(eval_settings, mcp_server, llm, RecordingTraceSink(), IDS[:1])

    assert result.aborted is False
    assert result.outcomes[0].status == "errored"
    assert result.outcomes[0].error == "ErrorReply"
    assert result.verdicts[0].status == "errored"


def test_an_errored_item_is_collected_exactly_once(
    eval_settings: EvalSettings, mcp_server: FastMCP
) -> None:
    llm = FakeLlm({Reformulation: [REFORMULATION] * 2, AnswerDraft: _unavailable(2)})

    result = _collect(eval_settings, mcp_server, llm, RecordingTraceSink(), IDS[:2])

    assert [o.status for o in result.outcomes] == ["errored", "errored"]
    assert _calls(llm, Reformulation) == 2
    assert _calls(llm, AnswerDraft) == 2


def test_the_limit_comes_from_the_settings(
    eval_settings: EvalSettings, mcp_server: FastMCP
) -> None:
    settings = eval_settings.model_copy(update={"max_consecutive_errors": 1})
    llm = FakeLlm({Reformulation: [REFORMULATION] * 5, AnswerDraft: _unavailable(5)})

    result = _collect(settings, mcp_server, llm, RecordingTraceSink(), IDS)

    assert result.aborted is True
    assert len(result.outcomes) == 1
    assert _calls(llm, AnswerDraft) == 1


def test_run_exits_1_and_prints_the_stop_message_when_aborted(
    eval_settings: EvalSettings, mcp_server: FastMCP
) -> None:
    _write_items(eval_settings, IDS)
    llm = FakeLlm({Reformulation: [REFORMULATION] * 5, AnswerDraft: _unavailable(5)})
    out = io.StringIO()

    code = cli.main(
        ["run"],
        llm_factory=lambda: llm,
        sink_factory=lambda _s: RecordingTraceSink(),
        settings=eval_settings,
        connector_factory=lambda _url: FastMcpConnector(mcp_server),
        out=out,
    )

    assert code == 1
    assert STOP_LINE in out.getvalue().splitlines()
    assert _calls(llm, AnswerDraft) == 3


def test_gate_over_an_aborted_run_fails_on_errored_items(
    eval_settings: EvalSettings, mcp_server: FastMCP
) -> None:
    _write_items(eval_settings, IDS)
    llm = FakeLlm({Reformulation: [REFORMULATION] * 5, AnswerDraft: _unavailable(5)})
    out = io.StringIO()

    code = cli.main(
        ["gate"],
        llm_factory=lambda: llm,
        sink_factory=lambda _s: RecordingTraceSink(),
        settings=eval_settings,
        connector_factory=lambda _url: FastMcpConnector(mcp_server),
        out=out,
    )

    text = out.getvalue()
    assert code == 1
    assert "GATE: FAIL" in text
    assert "FAIL errored: 3 items errored (incomplete run)" in text
    assert "GATE: PASS" not in text


@pytest.mark.parametrize("count", [1, 2])
def test_fewer_errors_than_the_limit_never_stop_the_run(
    count: int, eval_settings: EvalSettings, mcp_server: FastMCP
) -> None:
    llm = FakeLlm(
        {
            Reformulation: [REFORMULATION] * 3,
            AnswerDraft: [*_unavailable(count), *([GOOD_DRAFT] * (3 - count))],
        }
    )

    result = _collect(eval_settings, mcp_server, llm, RecordingTraceSink(), IDS[:3])

    assert result.aborted is False
    assert len(result.outcomes) == 3
