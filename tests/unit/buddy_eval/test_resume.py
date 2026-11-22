"""Resume, trace-existence check, stale-cache refusal and scored markers in the runner.

In-process only: scripted model, the in-process MCP server and a recording trace sink.
Synthetic data only.
"""

import asyncio
import dataclasses
import logging
from collections.abc import Callable, Sequence
from pathlib import Path

import pytest
from fastmcp import FastMCP
from tests.unit.buddy_eval.conftest import (
    GOOD_VERDICT,
    RecordingTraceSink,
    golden_item,
    write_golden,
)
from tests.unit.chat_bot.conftest import GOOD_DRAFT, REFORMULATION, FakeLlm
from tests.unit.mcp_server.conftest import MAPPED, PLAIN, make_content, write_index

from buddy_bot.mcp_client import FastMcpConnector
from buddy_bot.ports import LlmUnavailableError
from buddy_bot.schemas import AnswerDraft, Reformulation
from buddy_eval import cache as cache_module
from buddy_eval.cache import bot_version
from buddy_eval.config import EvalSettings
from buddy_eval.golden import GoldenItem, load_golden
from buddy_eval.judge import FactCheck, JudgeVerdict
from buddy_eval.runner import RunResult, run_items, scored_version
from buddy_eval.sources import SourceIndex
from buddy_eval.tracing import SCORER_SET_VERSION

A, B = "item-aa-01", "item-bb-01"


def _items(
    settings: EvalSettings, ids: Sequence[str], **overrides: object
) -> tuple[GoldenItem, ...]:
    write_golden(
        settings.golden_public_path, [golden_item("item-rej-01", "no_answer", review="rejected")]
    )
    write_golden(
        settings.golden_private_path, [golden_item(i, "handbook", **overrides) for i in ids]
    )
    return load_golden(settings.golden_public_path, settings.golden_private_path).approved()


def _llm(draft_items: Sequence[AnswerDraft | Exception]) -> FakeLlm:
    answered = sum(1 for draft in draft_items if isinstance(draft, AnswerDraft))
    return FakeLlm(
        {
            Reformulation: [REFORMULATION] * len(draft_items),
            AnswerDraft: list(draft_items),
            JudgeVerdict: [GOOD_VERDICT] * answered,
        }
    )


def _run(
    settings: EvalSettings,
    server: FastMCP,
    llm: FakeLlm,
    sink: RecordingTraceSink,
    items: Sequence[GoldenItem],
    sleep: Callable[[float], object] | None = None,
) -> RunResult:
    async def no_sleep(_seconds: float) -> None:
        return None

    async def go() -> RunResult:
        return await run_items(
            items,
            settings=settings,
            llm_factory=lambda: llm,
            connector_factory=lambda _url: FastMcpConnector(server),
            sink=sink,
            sleep=sleep or no_sleep,  # type: ignore[arg-type]
        )

    return asyncio.run(go())


def _outcome_files(settings: EvalSettings) -> list[Path]:
    return sorted((settings.private_dir / "eval" / "cache" / "outcome").glob("*.json"))


def test_a_first_run_caches_both_completed_outcomes_under_the_private_directory(
    eval_settings: EvalSettings, mcp_server: FastMCP
) -> None:
    sink = RecordingTraceSink()

    _run(eval_settings, mcp_server, _llm([GOOD_DRAFT] * 2), sink, _items(eval_settings, [A, B]))

    files = _outcome_files(eval_settings)
    assert len(sink.traced_calls) == 2
    assert len(files) == 2
    assert all(len(f.stem) == 64 for f in files)
    assert sink.score_calls[0].trace_ids == ("tr-1", "tr-2")


def test_a_full_rerun_makes_no_model_call_no_trace_and_no_feedback(
    eval_settings: EvalSettings, mcp_server: FastMCP
) -> None:
    sink = RecordingTraceSink()
    items = _items(eval_settings, [A, B])
    first = _run(eval_settings, mcp_server, _llm([GOOD_DRAFT] * 2), sink, items)
    silent = FakeLlm({})

    second = _run(eval_settings, mcp_server, silent, sink, items)

    assert silent.calls == []
    assert len(sink.traced_calls) == 2
    assert [c.trace_ids for c in sink.score_calls] == [("tr-1", "tr-2"), ()]
    assert second.verdicts == first.verdicts
    assert [o.trace_id for o in second.outcomes] == ["tr-1", "tr-2"]
    assert second.outcomes == first.outcomes
    assert len(_outcome_files(eval_settings)) == 2


def test_an_interrupted_run_resumes_calling_the_model_only_for_the_missing_item(
    eval_settings: EvalSettings, mcp_server: FastMCP
) -> None:
    settings = eval_settings.model_copy(update={"max_consecutive_errors": 1})
    sink = RecordingTraceSink()
    items = _items(settings, [A, B])
    first = _run(settings, mcp_server, _llm([GOOD_DRAFT, LlmUnavailableError("x")]), sink, items)
    assert first.aborted is True
    assert len(_outcome_files(settings)) == 1

    resumed_llm = _llm([GOOD_DRAFT])
    second = _run(settings, mcp_server, resumed_llm, sink, items)

    assert [c.schema for c in resumed_llm.calls].count(AnswerDraft) == 1
    assert [c.schema for c in resumed_llm.calls].count(Reformulation) == 1
    assert second.aborted is False
    assert [o.status for o in second.outcomes] == ["completed", "completed"]
    assert second.outcomes[0].trace_id == first.outcomes[0].trace_id
    assert len(_outcome_files(settings)) == 2
    # The first item was scored by the first run; the second run scores only the new trace.
    assert sink.score_calls[1].trace_ids == (second.outcomes[1].trace_id,)


def test_an_errored_outcome_is_never_cached_and_is_collected_again(
    eval_settings: EvalSettings, mcp_server: FastMCP
) -> None:
    sink = RecordingTraceSink()
    items = _items(eval_settings, [A])
    _run(eval_settings, mcp_server, _llm([LlmUnavailableError("x")]), sink, items)
    assert _outcome_files(eval_settings) == []

    second = _run(eval_settings, mcp_server, _llm([GOOD_DRAFT]), sink, items)

    assert second.outcomes[0].status == "completed"
    assert len(_outcome_files(eval_settings)) == 1


def test_a_cached_outcome_whose_trace_is_gone_is_collected_again_with_a_new_trace(
    eval_settings: EvalSettings, mcp_server: FastMCP
) -> None:
    sink = RecordingTraceSink()
    items = _items(eval_settings, [A])
    first = _run(eval_settings, mcp_server, _llm([GOOD_DRAFT]), sink, items)
    old_trace = first.outcomes[0].trace_id
    assert old_trace is not None
    sink.forget(old_trace)
    llm = _llm([GOOD_DRAFT])

    second = _run(eval_settings, mcp_server, llm, sink, items)

    assert llm.calls != []
    new_trace = second.outcomes[0].trace_id
    assert new_trace is not None
    assert new_trace != old_trace
    assert second.verdicts[0].trace_id == new_trace
    assert sink.score_calls[1].trace_ids == (new_trace,)
    # The cache now points at the live trace, so a third run is free again.
    silent = FakeLlm({})
    third = _run(eval_settings, mcp_server, silent, sink, items)
    assert silent.calls == []
    assert third.outcomes[0].trace_id == new_trace


def test_a_corrupt_cache_file_is_a_miss_and_the_item_is_collected_again(
    eval_settings: EvalSettings, mcp_server: FastMCP, caplog: pytest.LogCaptureFixture
) -> None:
    sink = RecordingTraceSink()
    items = _items(eval_settings, [A])
    _run(eval_settings, mcp_server, _llm([GOOD_DRAFT]), sink, items)
    (path,) = _outcome_files(eval_settings)
    path.write_text("{not json", encoding="utf-8")
    llm = _llm([GOOD_DRAFT])

    with caplog.at_level(logging.WARNING, logger="buddy_eval"):
        second = _run(eval_settings, mcp_server, llm, sink, items)

    assert second.outcomes[0].status == "completed"
    assert llm.calls != []
    warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert warnings == [f"cache file is not a JSON object: namespace=outcome key={path.stem}"]


def test_a_cache_payload_that_does_not_fit_the_item_is_a_miss(
    eval_settings: EvalSettings, mcp_server: FastMCP
) -> None:
    sink = RecordingTraceSink()
    items = _items(eval_settings, [A])
    _run(eval_settings, mcp_server, _llm([GOOD_DRAFT]), sink, items)
    (path,) = _outcome_files(eval_settings)
    path.write_text('{"item_id": "item-aa-01", "trace_id": "tr-1", "reply": {"kind": 5}}')
    llm = _llm([GOOD_DRAFT])

    second = _run(eval_settings, mcp_server, llm, sink, items)

    assert llm.calls != []
    assert second.outcomes[0].status == "completed"


def test_the_run_is_tagged_with_the_index_identity_the_bot_version_and_the_models(
    eval_settings: EvalSettings, mcp_server: FastMCP
) -> None:
    sink = RecordingTraceSink()

    result = _run(eval_settings, mcp_server, _llm([GOOD_DRAFT]), sink, _items(eval_settings, [A]))

    identity = SourceIndex.open(eval_settings.artifact_dir).identity
    (_name, tags) = sink.runs[0]
    assert result.identity == identity
    assert tags == {
        "items": "1",
        "index_content_hash": identity.content_hash,
        "guides_commit_sha": identity.guides_commit_sha,
        "build_id": identity.build_id,
        "bot_version": bot_version(),
        "reformulate_model": eval_settings.reformulate_model,
        "answer_model": eval_settings.answer_model,
    }


def test_a_missing_index_stops_the_run_naming_artifact_dir(
    eval_settings: EvalSettings, mcp_server: FastMCP, tmp_path: Path
) -> None:
    settings = eval_settings.model_copy(update={"artifact_dir": tmp_path / "nowhere"})
    sink = RecordingTraceSink()

    with pytest.raises(FileNotFoundError, match="ARTIFACT_DIR"):
        _run(settings, mcp_server, FakeLlm({}), sink, _items(settings, [A]))

    assert sink.runs == []


def _with_model(settings: EvalSettings, tmp_path: Path) -> EvalSettings:
    return settings.model_copy(update={"answer_model": "test-other-sonnet"})


def _with_reformulate_model(settings: EvalSettings, tmp_path: Path) -> EvalSettings:
    return settings.model_copy(update={"reformulate_model": "test-other-haiku"})


def _with_threshold(settings: EvalSettings, tmp_path: Path) -> EvalSettings:
    return settings.model_copy(update={"confidence_threshold": 0.9})


def _with_other_guides_commit(settings: EvalSettings, tmp_path: Path) -> EvalSettings:
    directory = tmp_path / "other-commit"
    write_index(directory, dataclasses.replace(make_content(), guides_commit_sha="2" * 40))
    return settings.model_copy(update={"artifact_dir": directory})


def _with_other_index_content(settings: EvalSettings, tmp_path: Path) -> EvalSettings:
    directory = tmp_path / "other-content"
    write_index(directory, make_content(chunks=(MAPPED, PLAIN)))
    return settings.model_copy(update={"artifact_dir": directory})


@pytest.mark.parametrize(
    "change",
    [
        _with_model,
        _with_reformulate_model,
        _with_threshold,
        _with_other_guides_commit,
        _with_other_index_content,
    ],
)
def test_a_changed_setting_or_index_never_reuses_a_cached_outcome(
    eval_settings: EvalSettings,
    mcp_server: FastMCP,
    tmp_path: Path,
    change: Callable[[EvalSettings, Path], EvalSettings],
) -> None:
    sink = RecordingTraceSink()
    items = _items(eval_settings, [A])
    _run(eval_settings, mcp_server, _llm([GOOD_DRAFT]), sink, items)
    llm = _llm([GOOD_DRAFT])

    _run(change(eval_settings, tmp_path), mcp_server, llm, sink, items)

    assert llm.calls != []
    assert len(sink.traced_calls) == 2


def test_a_changed_golden_item_text_is_collected_again_and_its_neighbour_is_not(
    eval_settings: EvalSettings, mcp_server: FastMCP
) -> None:
    sink = RecordingTraceSink()
    _run(
        eval_settings,
        mcp_server,
        _llm([GOOD_DRAFT] * 2),
        sink,
        _items(eval_settings, [A, B]),
    )
    edited = list(_items(eval_settings, [A, B]))
    edited[0] = edited[0].model_copy(update={"question": "an edited synthetic question"})
    llm = _llm([GOOD_DRAFT])

    _run(eval_settings, mcp_server, llm, sink, edited)

    assert [c.schema for c in llm.calls].count(AnswerDraft) == 1
    assert len(sink.traced_calls) == 3


def test_a_changed_bot_version_never_reuses_a_cached_outcome(
    eval_settings: EvalSettings,
    mcp_server: FastMCP,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sink = RecordingTraceSink()
    items = _items(eval_settings, [A])
    _run(eval_settings, mcp_server, _llm([GOOD_DRAFT]), sink, items)
    edited_bot = tmp_path / "edited-bot"
    edited_bot.mkdir()
    (edited_bot / "prompts.py").write_text("SYSTEM = 'edited'\n", encoding="utf-8")
    monkeypatch.setattr(cache_module, "BOT_DIR", edited_bot)
    llm = _llm([GOOD_DRAFT])

    _run(eval_settings, mcp_server, llm, sink, items)

    assert llm.calls != []
    assert len(sink.traced_calls) == 2


def test_scoring_feedback_is_attached_once_per_trace_and_scorer_set_version(
    eval_settings: EvalSettings, mcp_server: FastMCP, monkeypatch: pytest.MonkeyPatch
) -> None:
    sink = RecordingTraceSink()
    items = _items(eval_settings, [A])
    first = _run(eval_settings, mcp_server, _llm([GOOD_DRAFT]), sink, items)
    scored_dir = eval_settings.private_dir / "eval" / "cache" / "scored"
    marker = f"tr-1-{scored_version(first.verdicts[0])}.json"
    assert marker.startswith(f"tr-1-{SCORER_SET_VERSION}-")
    assert [p.name for p in scored_dir.glob("*.json")] == [marker]

    _run(eval_settings, mcp_server, FakeLlm({}), sink, items)
    assert [c.trace_ids for c in sink.score_calls] == [("tr-1",), ()]

    # A new scorer set re-scores the same trace once (A-07-3).
    monkeypatch.setattr("buddy_eval.runner.SCORER_SET_VERSION", f"{SCORER_SET_VERSION}-next")
    _run(eval_settings, mcp_server, FakeLlm({}), sink, items)
    _run(eval_settings, mcp_server, FakeLlm({}), sink, items)

    assert [c.trace_ids for c in sink.score_calls] == [("tr-1",), (), ("tr-1",), ()]


# The judge now finds the one key fact missing: a different verdict for the same item.
MISSING_VERDICT = JudgeVerdict(
    facts=[FactCheck(fact="synthetic fact", present=False, contradicted=False)],
    invented_claims=[],
    reasoning="synthetic reasoning, fact missing",
)
OTHER_DRAFT = GOOD_DRAFT.model_copy(update={"answer": "Una risposta sintetica diversa."})


def _judge_calls(llm: FakeLlm) -> int:
    return [c.schema for c in llm.calls].count(JudgeVerdict)


def test_a_recollected_item_with_a_different_reply_is_judged_again(
    eval_settings: EvalSettings, mcp_server: FastMCP
) -> None:
    sink = RecordingTraceSink()
    items = _items(eval_settings, [A])
    first = _run(eval_settings, mcp_server, _llm([GOOD_DRAFT]), sink, items)
    assert first.verdicts[0].status == "correct"
    sink.forget("tr-1")
    llm = FakeLlm(
        {
            Reformulation: [REFORMULATION],
            AnswerDraft: [OTHER_DRAFT],
            JudgeVerdict: [MISSING_VERDICT],
        }
    )

    second = _run(eval_settings, mcp_server, llm, sink, items)

    assert _judge_calls(llm) == 1
    verdict = second.verdicts[0]
    assert verdict.trace_id == "tr-2"
    assert verdict.judge == MISSING_VERDICT
    assert verdict.status == "wrong"
    assert sink.score_calls[1].trace_ids == ("tr-2",)
    assert sink.score_calls[1].verdicts["tr-2"] == verdict


def test_a_recollected_item_with_an_identical_reply_reuses_the_cached_verdict(
    eval_settings: EvalSettings, mcp_server: FastMCP
) -> None:
    sink = RecordingTraceSink()
    items = _items(eval_settings, [A])
    first = _run(eval_settings, mcp_server, _llm([GOOD_DRAFT]), sink, items)
    sink.forget("tr-1")
    # No judge answer is scripted: a judge call would error the item.
    llm = FakeLlm({Reformulation: [REFORMULATION], AnswerDraft: [GOOD_DRAFT]})

    second = _run(eval_settings, mcp_server, llm, sink, items)

    assert _judge_calls(llm) == 0
    assert second.outcomes[0].status == "completed"
    assert second.verdicts[0].judge == first.verdicts[0].judge
    assert sink.score_calls[1].trace_ids == ("tr-2",)


def test_an_already_scored_trace_whose_verdict_changes_is_scored_again(
    eval_settings: EvalSettings, mcp_server: FastMCP
) -> None:
    sink = RecordingTraceSink()
    items = _items(eval_settings, [A])
    _run(eval_settings, mcp_server, _llm([GOOD_DRAFT]), sink, items)
    # A new judge model changes the verdict key while the outcome and its trace stay cached.
    other_judge = eval_settings.model_copy(update={"judge_model": "test-other-judge"})
    llm = FakeLlm({JudgeVerdict: [MISSING_VERDICT]})

    second = _run(other_judge, mcp_server, llm, sink, items)

    assert _judge_calls(llm) == 1
    assert len(sink.traced_calls) == 1
    assert sink.score_calls[1].trace_ids == ("tr-1",)
    assert sink.score_calls[1].verdicts["tr-1"] == second.verdicts[0]
    assert second.verdicts[0].status == "wrong"


def test_an_already_scored_trace_whose_verdict_is_unchanged_is_not_scored_again(
    eval_settings: EvalSettings, mcp_server: FastMCP
) -> None:
    sink = RecordingTraceSink()
    items = _items(eval_settings, [A])
    _run(eval_settings, mcp_server, _llm([GOOD_DRAFT]), sink, items)
    other_judge = eval_settings.model_copy(update={"judge_model": "test-other-judge"})
    llm = FakeLlm({JudgeVerdict: [GOOD_VERDICT]})

    _run(other_judge, mcp_server, llm, sink, items)

    assert _judge_calls(llm) == 1
    assert [c.trace_ids for c in sink.score_calls] == [("tr-1",), ()]


def test_the_pause_applies_only_to_items_that_are_collected(
    eval_settings: EvalSettings, mcp_server: FastMCP
) -> None:
    settings = eval_settings.model_copy(update={"item_pause_seconds": 0.5})
    sink = RecordingTraceSink()
    slept: list[float] = []

    async def record(seconds: float) -> None:
        slept.append(seconds)

    _run(settings, mcp_server, _llm([GOOD_DRAFT]), sink, _items(settings, [A]), record)
    assert slept == []

    # A is cached: B is the first item actually collected, so there is nothing to pace after.
    _run(settings, mcp_server, _llm([GOOD_DRAFT]), sink, _items(settings, [A, B]), record)
    assert slept == []

    _run(
        settings,
        mcp_server,
        _llm([GOOD_DRAFT] * 2),
        sink,
        _items(settings, ["item-cc-01", "item-dd-01"]),
        record,
    )
    assert slept == [0.5]
