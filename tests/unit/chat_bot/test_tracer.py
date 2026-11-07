"""Tracer: a recorded DM becomes a placeholder, then a cited answer over the real MCP server.

Also pins the citation gate contract (D-01, D-02).
"""

import re
from typing import Any

import pytest
from tests.unit.chat_bot.conftest import (
    GOOD_DRAFT,
    REFORMULATION,
    FakeChatApi,
    FakeLlm,
    RecordingConnector,
    ServiceFactory,
    load_event,
)

from buddy_bot.gate import check, cited_sources
from buddy_bot.schemas import AnswerDraft, Evidence, Reformulation
from buddy_bot.service import PLACEHOLDER_TEXT

pytestmark = pytest.mark.anyio

THRESHOLD = 0.7
EVIDENCE = Evidence(
    source_url="handbook://02-ferie",
    kind="handbook",
    title="Ferie e permessi",
    text="Invia la richiesta al responsabile.",
    revision_date="2026-10-03T00:00:00+00:00",
    revision_kind="last_updated",
)


async def test_dm_gets_placeholder_then_cited_answer(
    connector: RecordingConnector, make_service: ServiceFactory
) -> None:
    llm = FakeLlm({Reformulation: [REFORMULATION], AnswerDraft: [GOOD_DRAFT]})
    chat = FakeChatApi()
    service = make_service(llm, chat=chat)

    await service.handle(load_event("legacy_dm_message"))

    assert len(chat.created) == 1
    created = chat.created[0]
    assert created.text == PLACEHOLDER_TEXT == "Sto cercando nelle fonti…"
    assert created.space == "spaces/AAAAsyntheticDM"
    assert created.thread == "spaces/AAAAsyntheticDM/threads/thr-1"
    assert len(chat.updated) == 1
    updated = chat.updated[0]
    assert updated.name == f"{created.space}/messages/placeholder-1"
    assert GOOD_DRAFT.answer in updated.text
    assert "handbook://02-ferie" in updated.text
    assert "revisione 2026-10-03" in updated.text

    answer_call = llm.calls[-1]
    assert answer_call.schema is AnswerDraft
    assert answer_call.model == "test-sonnet"
    assert '<fonte id="handbook://02-ferie"' in answer_call.user
    prompt_ids = set(re.findall(r'<fonte id="([^"]+)"', answer_call.user))
    assert prompt_ids
    assert prompt_ids <= set(connector.returned_urls)
    assert set(connector.calls) == {"handbook_search", "guides_search"}


async def test_addon_room_mention_gets_placeholder_in_thread_then_answer(
    connector: RecordingConnector, make_service: ServiceFactory
) -> None:
    llm = FakeLlm({Reformulation: [REFORMULATION], AnswerDraft: [GOOD_DRAFT]})
    chat = FakeChatApi()

    await make_service(llm, chat=chat).handle(load_event("addon_room_mention"))

    assert len(chat.created) == 1
    created = chat.created[0]
    assert created.text == PLACEHOLDER_TEXT
    assert created.space == "spaces/AAAAsyntheticRoom"
    assert created.thread == "spaces/AAAAsyntheticRoom/threads/t-1"
    assert len(chat.updated) == 1
    updated = chat.updated[0]
    assert updated.name == f"{created.space}/messages/placeholder-1"
    assert GOOD_DRAFT.answer in updated.text
    assert "handbook://02-ferie" in updated.text
    reformulate_call = llm.calls[0]
    assert reformulate_call.schema is Reformulation
    assert "Come richiedo le ferie?" in reformulate_call.user
    assert "@AI Buddy" not in reformulate_call.user


async def test_forged_citation_is_refused(
    connector: RecordingConnector, make_service: ServiceFactory
) -> None:
    forged = GOOD_DRAFT.model_copy(update={"citations": ["handbook://99-inventata"]})
    llm = FakeLlm({Reformulation: [REFORMULATION], AnswerDraft: [forged]})
    chat = FakeChatApi()

    await make_service(llm, chat=chat).handle(load_event("legacy_dm_message"))

    assert len(chat.updated) == 1
    assert chat.updated[0].text == "Non lo so, chiedi a HR."
    assert GOOD_DRAFT.answer not in chat.updated[0].text


async def test_stranger_reaches_nothing(
    connector: RecordingConnector, make_service: ServiceFactory
) -> None:
    event: dict[str, Any] = load_event("legacy_dm_message")
    event["user"] = {"name": "users/999", "email": "altro@example.invalid", "type": "HUMAN"}
    llm = FakeLlm({Reformulation: [REFORMULATION], AnswerDraft: [GOOD_DRAFT]})
    chat = FakeChatApi()

    await make_service(llm, chat=chat).handle(event)

    assert llm.calls == []
    assert connector.calls == []
    assert chat.created == [] and chat.updated == []


def _draft(**changes: Any) -> AnswerDraft:
    return GOOD_DRAFT.model_copy(update=changes)


@pytest.mark.parametrize(
    ("evidence", "draft", "reason"),
    [
        ({}, GOOD_DRAFT, "no_evidence"),
        ({EVIDENCE.source_url: EVIDENCE}, _draft(citations=[]), "no_citation"),
        (
            {EVIDENCE.source_url: EVIDENCE},
            _draft(citations=["handbook://99-inventata"]),
            "unsupported_citation",
        ),
        ({EVIDENCE.source_url: EVIDENCE}, _draft(grounded=False), "not_grounded"),
        ({EVIDENCE.source_url: EVIDENCE}, _draft(confidence=0.69), "low_confidence"),
        # Two rules broken at once: the earlier check in the fixed order names the reason.
        ({EVIDENCE.source_url: EVIDENCE}, _draft(citations=[], grounded=False), "no_citation"),
        ({EVIDENCE.source_url: EVIDENCE}, _draft(confidence=0.7), "ok"),
    ],
    ids=[
        "no_evidence",
        "no_citation",
        "unsupported_citation",
        "not_grounded",
        "low_confidence",
        "order_no_citation_before_not_grounded",
        "passes_at_threshold",
    ],
)
def test_gate_reasons_in_fixed_order(
    evidence: dict[str, Evidence], draft: AnswerDraft, reason: str
) -> None:
    result = check(evidence, draft, THRESHOLD)
    assert result.reason == reason
    assert result.ok is (reason == "ok")


def test_cited_sources_returns_each_source_once_after_strip() -> None:
    draft = _draft(citations=[" handbook://02-ferie", "handbook://02-ferie"])
    assert cited_sources({EVIDENCE.source_url: EVIDENCE}, draft) == [EVIDENCE]
