"""Workflow decisions over the real in-memory MCP server and a scripted model."""

import logging
import re
from pathlib import Path
from typing import Any

import pytest
from fastmcp import Client, FastMCP
from tests.unit.chat_bot.conftest import FakeLlm, RecordingConnector
from tests.unit.mcp_server.conftest import PLAIN, SHA, WEB_BASE

from buddy_bot.mcp_client import FastMcpConnector
from buddy_bot.ports import LlmOutputError, LlmUnavailableError, Turn
from buddy_bot.prompts import KEYWORD_BRIDGE
from buddy_bot.schemas import (
    AnswerDraft,
    BotReply,
    ContactExtraction,
    Reformulation,
    RetryPlan,
)
from buddy_bot.workflow import WorkflowConfig, WorkflowDeps, guides_question_query, run_workflow
from buddy_mcp.gaplog import InMemoryGapLog
from buddy_mcp.guides_tools import guides_permalink

pytestmark = pytest.mark.anyio

SKILL = Path(__file__).resolve().parents[3] / "skills" / "digitiamo-buddy" / "SKILL.md"
# "gateway" appears only in the PLAIN Guides chunk of the test index.
GATEWAY_QUESTION = "Come configuro il gateway?"
GATEWAY_URL = guides_permalink(WEB_BASE, SHA, PLAIN)


def _reformulation(
    keywords_it: list[str] | None = None,
    keywords_en: list[str] | None = None,
    intent: str = "question",
    standalone_question: str = "Come richiedo le ferie?",
) -> Reformulation:
    return Reformulation.model_validate(
        {
            "standalone_question": standalone_question,
            "keywords_it": keywords_it or ["ferie"],
            "keywords_en": keywords_en or ["chunking"],
            "intent": intent,
            "sensitive_topic": None,
        }
    )


def _draft(citation: str, confidence: float = 0.9) -> AnswerDraft:
    return AnswerDraft(
        answer="Risposta dal manuale.",
        citations=[citation],
        grounded=True,
        confidence=confidence,
    )


async def _run(
    llm: FakeLlm,
    connector: RecordingConnector,
    config: WorkflowConfig,
    history: list[Turn] | None = None,
) -> BotReply:
    return await run_workflow("domanda", history or [], WorkflowDeps(llm, connector, config))


def _count(llm: FakeLlm, schema: type) -> int:
    return sum(1 for call in llm.calls if call.schema is schema)


async def test_low_confidence_then_good_second_draft_answers_over_both_attempts(
    connector: RecordingConnector, workflow_config: WorkflowConfig, gaplog: InMemoryGapLog
) -> None:
    llm = FakeLlm(
        {
            Reformulation: [_reformulation()],
            AnswerDraft: [_draft("handbook://02-ferie", 0.2), _draft("handbook://03-malattia")],
            RetryPlan: [RetryPlan(keywords_it=["malattia"], keywords_en=["retrieval"])],
        }
    )

    reply = await _run(llm, connector, workflow_config)

    assert reply.kind == "answer"
    assert [s.source_url for s in reply.sources] == ["handbook://03-malattia"]
    assert _count(llm, RetryPlan) == 1
    second_prompt = [c for c in llm.calls if c.schema is AnswerDraft][1].user
    assert 'id="handbook://02-ferie"' in second_prompt
    assert 'id="handbook://03-malattia"' in second_prompt
    assert reply.gap_reported is False
    assert gaplog.records == []
    assert "buddy_report_gap" not in connector.calls


async def test_attempt_with_no_results_does_not_call_the_answer_model(
    connector: RecordingConnector, workflow_config: WorkflowConfig
) -> None:
    llm = FakeLlm(
        {
            Reformulation: [_reformulation(["zzzz"], ["zzzz"])],
            AnswerDraft: [_draft("handbook://02-ferie")],
            RetryPlan: [RetryPlan(keywords_it=["ferie"], keywords_en=["chunking"])],
        }
    )

    reply = await _run(llm, connector, workflow_config)

    assert reply.kind == "answer"
    assert _count(llm, AnswerDraft) == 1


async def test_both_attempts_without_results_refuse_without_any_answer_call(
    connector: RecordingConnector, workflow_config: WorkflowConfig, gaplog: InMemoryGapLog
) -> None:
    llm = FakeLlm(
        {
            Reformulation: [_reformulation(["zzzz"], ["zzzz"])],
            RetryPlan: [RetryPlan(keywords_it=["yyyy"], keywords_en=["yyyy"])],
        }
    )

    reply = await _run(llm, connector, workflow_config)

    assert reply.kind == "refusal"
    assert reply.gate_reason == "no_evidence"
    assert _count(llm, AnswerDraft) == 0
    assert len(gaplog.records) == 1


async def test_retry_plan_failure_skips_the_retry_and_refuses(
    connector: RecordingConnector, workflow_config: WorkflowConfig, gaplog: InMemoryGapLog
) -> None:
    llm = FakeLlm(
        {
            Reformulation: [_reformulation()],
            AnswerDraft: [_draft("handbook://02-ferie", 0.1)],
            RetryPlan: [LlmOutputError("bad json")],
        }
    )

    reply = await _run(llm, connector, workflow_config)

    assert reply.kind == "refusal"
    assert reply.gate_reason == "low_confidence"
    assert _count(llm, AnswerDraft) == 1
    assert len(gaplog.records) == 1


async def test_invalid_answer_output_counts_as_a_failed_gate(
    connector: RecordingConnector, workflow_config: WorkflowConfig
) -> None:
    llm = FakeLlm(
        {
            Reformulation: [_reformulation()],
            AnswerDraft: [LlmOutputError("bad"), LlmOutputError("bad")],
            RetryPlan: [RetryPlan(keywords_it=["permessi"], keywords_en=["leave"])],
        }
    )

    reply = await _run(llm, connector, workflow_config)

    assert reply.kind == "refusal"
    assert reply.gate_reason == "invalid_output"
    assert _count(llm, AnswerDraft) == 2


@pytest.mark.parametrize("intent", ["chitchat", "off_topic"])
async def test_chitchat_and_off_topic_get_smalltalk_with_no_retrieval_and_no_gap(
    intent: str,
    connector: RecordingConnector,
    workflow_config: WorkflowConfig,
    gaplog: InMemoryGapLog,
) -> None:
    llm = FakeLlm({Reformulation: [_reformulation(intent=intent)]})

    reply = await _run(llm, connector, workflow_config)

    assert reply.kind == "smalltalk"
    assert connector.calls == []
    assert [c.schema for c in llm.calls] == [Reformulation]
    assert gaplog.records == []


async def test_history_reaches_only_the_reformulation_prompt(
    connector: RecordingConnector, workflow_config: WorkflowConfig
) -> None:
    llm = FakeLlm(
        {
            Reformulation: [_reformulation()],
            AnswerDraft: [_draft("handbook://02-ferie", 0.1), _draft("handbook://02-ferie")],
            RetryPlan: [RetryPlan(keywords_it=["permessi"], keywords_en=["leave"])],
        }
    )

    reply = await _run(llm, connector, workflow_config, [Turn("q-storia-1", "a-storia-1")])

    assert reply.kind == "answer"
    reformulate_call = llm.calls[0]
    assert reformulate_call.schema is Reformulation
    assert "q-storia-1" in reformulate_call.user
    for call in llm.calls[1:]:
        assert "q-storia-1" not in call.user + call.system
        assert "a-storia-1" not in call.user + call.system


async def test_reformulation_failing_twice_gives_the_error_reply_without_tools_or_gap(
    connector: RecordingConnector, workflow_config: WorkflowConfig, gaplog: InMemoryGapLog
) -> None:
    llm = FakeLlm({Reformulation: [LlmOutputError("bad"), LlmOutputError("bad")]})

    reply = await _run(llm, connector, workflow_config)

    assert reply.kind == "error"
    assert connector.calls == []
    assert gaplog.records == []


async def test_model_unavailable_during_reformulation_gives_the_error_reply(
    connector: RecordingConnector, workflow_config: WorkflowConfig, gaplog: InMemoryGapLog
) -> None:
    llm = FakeLlm({Reformulation: [LlmUnavailableError("down")]})

    reply = await _run(llm, connector, workflow_config)

    assert reply.kind == "error"
    assert connector.calls == []
    assert gaplog.records == []


async def test_reformulation_failure_is_logged_with_the_error_type_only(
    connector: RecordingConnector,
    workflow_config: WorkflowConfig,
    caplog: pytest.LogCaptureFixture,
) -> None:
    # 04-26 gap: a lost Meridian login ended every question in the error reply with no log line.
    llm = FakeLlm({Reformulation: [LlmUnavailableError("AuthenticationError")]})

    with caplog.at_level(logging.ERROR, logger="buddy_bot"):
        await _run(llm, connector, workflow_config)

    messages = [r.getMessage() for r in caplog.records if r.levelno == logging.ERROR]
    assert messages == ["reformulate failed: LlmUnavailableError: AuthenticationError"]


async def test_model_unavailable_during_answer_propagates_without_a_gap(
    connector: RecordingConnector, workflow_config: WorkflowConfig, gaplog: InMemoryGapLog
) -> None:
    llm = FakeLlm({Reformulation: [_reformulation()], AnswerDraft: [LlmUnavailableError("down")]})

    with pytest.raises(LlmUnavailableError):
        await _run(llm, connector, workflow_config)

    assert gaplog.records == []
    assert "buddy_report_gap" not in connector.calls


async def test_contact_lookup_failure_never_breaks_the_refusal(
    connector: RecordingConnector, workflow_config: WorkflowConfig
) -> None:
    llm = FakeLlm(
        {
            Reformulation: [_reformulation()],
            AnswerDraft: [_draft("handbook://99-x"), _draft("handbook://98-x")],
            RetryPlan: [RetryPlan(keywords_it=["permessi"], keywords_en=["leave"])],
            ContactExtraction: [LlmUnavailableError("down")],
        }
    )

    reply = await _run(llm, connector, workflow_config)

    assert reply.kind == "refusal"
    assert reply.referente is not None
    assert reply.referente.contact is None


def _answer_prompts(llm: FakeLlm) -> list[str]:
    return [c.user for c in llm.calls if c.schema is AnswerDraft]


_UNGROUNDED = AnswerDraft(answer="Non lo so.", citations=[], grounded=False, confidence=0.9)


async def test_question_text_reaches_a_second_guides_search_and_the_answer_prompt(
    connector: RecordingConnector, workflow_config: WorkflowConfig
) -> None:
    llm = FakeLlm(
        {
            Reformulation: [
                _reformulation(["zzzz"], ["zzzz"], standalone_question=GATEWAY_QUESTION)
            ],
            AnswerDraft: [_draft(GATEWAY_URL)],
        }
    )

    reply = await _run(llm, connector, workflow_config)

    assert connector.calls == ["handbook_search", "guides_search", "guides_search"]
    assert f'<fonte id="{GATEWAY_URL}"' in _answer_prompts(llm)[0]
    assert reply.kind == "answer"
    assert [s.source_url for s in reply.sources] == [GATEWAY_URL]


async def test_question_only_evidence_never_bypasses_the_gate(
    connector: RecordingConnector, workflow_config: WorkflowConfig, gaplog: InMemoryGapLog
) -> None:
    llm = FakeLlm(
        {
            Reformulation: [
                _reformulation(["zzzz"], ["zzzz"], standalone_question=GATEWAY_QUESTION)
            ],
            AnswerDraft: [_UNGROUNDED, _UNGROUNDED],
            RetryPlan: [RetryPlan(keywords_it=["malattia"], keywords_en=["zzzz"])],
        }
    )

    reply = await _run(llm, connector, workflow_config)

    assert _count(llm, AnswerDraft) == 2
    assert reply.kind == "refusal"
    assert reply.gate_reason == "no_citation"  # the gate checks citations before grounded
    assert reply.answer == ""
    assert reply.sources == []
    assert len(gaplog.records) == 1


async def test_a_chunk_found_by_both_guides_searches_enters_the_prompt_once(
    connector: RecordingConnector, workflow_config: WorkflowConfig
) -> None:
    llm = FakeLlm(
        {
            Reformulation: [
                _reformulation(["zzzz"], ["gateway"], standalone_question=GATEWAY_QUESTION)
            ],
            AnswerDraft: [_draft(GATEWAY_URL)],
        }
    )

    reply = await _run(llm, connector, workflow_config)

    assert reply.kind == "answer"
    assert connector.calls == ["handbook_search", "guides_search", "guides_search"]
    assert _answer_prompts(llm)[0].count(f'<fonte id="{GATEWAY_URL}"') == 1


async def test_retry_runs_only_keyword_searches_and_keeps_question_evidence(
    connector: RecordingConnector, workflow_config: WorkflowConfig
) -> None:
    llm = FakeLlm(
        {
            Reformulation: [
                _reformulation(["zzzz"], ["zzzz"], standalone_question=GATEWAY_QUESTION)
            ],
            AnswerDraft: [_draft(GATEWAY_URL, 0.2), _draft("handbook://02-ferie")],
            RetryPlan: [RetryPlan(keywords_it=["ferie"], keywords_en=["zzzz"])],
        }
    )

    reply = await _run(llm, connector, workflow_config)

    assert reply.kind == "answer"
    assert connector.calls == [
        "handbook_search",
        "guides_search",
        "guides_search",
        "handbook_search",
        "guides_search",
    ]
    assert connector.calls.count("guides_search") == 3
    second_prompt = _answer_prompts(llm)[1]
    assert f'<fonte id="{GATEWAY_URL}"' in second_prompt
    assert '<fonte id="handbook://02-ferie"' in second_prompt


async def test_first_attempt_tried_lists_the_question_search_after_the_keyword_searches(
    connector: RecordingConnector, workflow_config: WorkflowConfig, gaplog: InMemoryGapLog
) -> None:
    llm = FakeLlm(
        {
            Reformulation: [
                _reformulation(["zzzz"], ["zzzz"], standalone_question=GATEWAY_QUESTION)
            ],
            AnswerDraft: [_UNGROUNDED],
            RetryPlan: [LlmOutputError("bad json")],
        }
    )

    reply = await _run(llm, connector, workflow_config)

    assert reply.kind == "refusal"
    assert len(gaplog.records) == 1
    assert list(gaplog.records[0].tried) == [
        "handbook_search: zzzz",
        "guides_search: zzzz",
        "guides_search: configuro gateway?",
    ]


@pytest.mark.parametrize(
    ("question", "expected"),
    [
        (
            "Come si sceglie tra stdio e Streamable HTTP in un server MCP?",
            "sceglie stdio Streamable HTTP server MCP?",
        ),
        ("Perché il deploy NON va?", "deploy"),
        ("Come e perché?", ""),
        ("", ""),
    ],
)
def test_guides_question_query_drops_italian_function_words(question: str, expected: str) -> None:
    assert guides_question_query(question) == expected


async def test_a_question_of_only_function_words_makes_no_question_search(
    connector: RecordingConnector, workflow_config: WorkflowConfig
) -> None:
    llm = FakeLlm(
        {
            Reformulation: [_reformulation(standalone_question="Come e perché?")],
            AnswerDraft: [_draft("handbook://02-ferie")],
        }
    )

    reply = await _run(llm, connector, workflow_config)

    assert reply.kind == "answer"
    assert connector.calls == ["handbook_search", "guides_search"]


async def test_default_connector_sends_guides_limit_8_and_handbook_limit_3(
    mcp_server: FastMCP, monkeypatch: pytest.MonkeyPatch
) -> None:
    sent: list[tuple[str, Any]] = []
    original = Client.call_tool

    async def recording(self: Client[Any], name: str, arguments: Any = None, **kw: Any) -> Any:
        sent.append((name, (arguments or {}).get("limit")))
        return await original(self, name, arguments, **kw)

    monkeypatch.setattr(Client, "call_tool", recording)

    async with FastMcpConnector(mcp_server).session() as tools:
        await tools.guides_search("chunking")
        await tools.handbook_search("ferie")

    assert sent == [("guides_search", 8), ("handbook_search", 3)]


def _skill_bridge_rows() -> tuple[tuple[str, str], ...]:
    lines = SKILL.read_text(encoding="utf-8").splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith("## Italiano -> inglese"))
    rows: list[tuple[str, str]] = []
    for line in lines[start + 1 :]:
        if line.startswith("## "):
            break
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if line.startswith("|") and len(cells) == 2 and not re.fullmatch(r"-+", cells[0]):
            rows.append((cells[0], cells[1]))
    return tuple(rows[1:])  # drop the header row


def test_keyword_bridge_equals_the_skill_table() -> None:
    assert _skill_bridge_rows() == KEYWORD_BRIDGE
