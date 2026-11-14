"""The compose stub LLM honours the contract of the bot's real client (INFRA-02, offline)."""

import json
import logging
from collections.abc import AsyncIterator
from typing import Any

import httpx2
import pytest
from anthropic import AsyncAnthropic
from pydantic import BaseModel

import stub_llm
from buddy_bot.llm import AnthropicMessagesClient, _json_instruction
from buddy_bot.prompts import format_evidence
from buddy_bot.schemas import (
    AnswerDraft,
    ContactExtraction,
    Evidence,
    Reformulation,
    RetryPlan,
)

pytestmark = pytest.mark.anyio

QUESTION = "Come richiedo le ferie?"
HANDBOOK_ID = "handbook://02-ferie"
OTHER_ID = "handbook://01-benvenuto"
EVIDENCE = (
    Evidence(
        source_url=HANDBOOK_ID,
        kind="handbook",
        title="Ferie",
        text="Come richiedere le ferie. Scrivi alle risorse umane.",
        revision_date="2026-10-03",
        revision_kind="last_updated",
    ),
    Evidence(
        source_url=OTHER_ID,
        kind="handbook",
        title="Benvenuto",
        text="Benvenuto in azienda.",
        revision_date="2026-09-02",
        revision_kind="last_updated",
    ),
)


@pytest.fixture
async def http() -> AsyncIterator[httpx2.AsyncClient]:
    transport = httpx2.ASGITransport(app=stub_llm.app)
    async with httpx2.AsyncClient(transport=transport, base_url="http://stub-llm:8090") as client:
        yield client


def _request(schema: type[BaseModel], user: str) -> dict[str, Any]:
    """The body the bot's client posts: the instruction and schema are appended to `system`."""
    return {
        "model": "claude-test",
        "max_tokens": 100,
        "system": f"Sei un assistente.\n\n{_json_instruction(schema)}",
        "messages": [{"role": "user", "content": user}],
    }


async def _text(http: httpx2.AsyncClient, body: dict[str, Any]) -> str:
    response = await http.post("/v1/messages", json=body)
    assert response.status_code == 200
    payload = response.json()
    assert payload["type"] == "message" and payload["role"] == "assistant"
    assert payload["model"] == "claude-test"
    assert payload["stop_reason"] == "end_turn"
    assert payload["usage"] == {"input_tokens": 0, "output_tokens": 0}
    blocks = payload["content"]
    assert len(blocks) == 1 and blocks[0]["type"] == "text"
    return str(blocks[0]["text"])


@pytest.mark.parametrize(
    ("schema", "user"),
    [
        (Reformulation, QUESTION),
        (RetryPlan, f"Domanda: {QUESTION}\nRicerche già provate: handbook_search: ferie"),
        (ContactExtraction, f"Domanda: {QUESTION}\n\n{format_evidence(EVIDENCE)}"),
        (AnswerDraft, f"Domanda: {QUESTION}\n\n{format_evidence(EVIDENCE)}"),
    ],
)
async def test_each_workflow_schema_gets_one_text_block_the_real_class_accepts(
    http: httpx2.AsyncClient, schema: type[BaseModel], user: str
) -> None:
    text = await _text(http, _request(schema, user))
    assert schema.model_validate_json(text)


async def test_reformulation_keeps_the_last_line_and_up_to_five_keywords(
    http: httpx2.AsyncClient,
) -> None:
    user = "Domanda: altra\nRisposta: x\n\nMessaggio: Come richiedo le ferie estive per favore?"
    reformulation = Reformulation.model_validate_json(
        await _text(http, _request(Reformulation, user))
    )
    assert reformulation.standalone_question.startswith("Messaggio: Come richiedo")
    assert 1 <= len(reformulation.keywords_it) <= stub_llm.MAX_KEYWORDS
    assert reformulation.intent == "question"
    assert reformulation.sensitive_topic is None


async def test_a_question_without_long_words_still_has_a_keyword(
    http: httpx2.AsyncClient,
) -> None:
    reformulation = Reformulation.model_validate_json(
        await _text(http, _request(Reformulation, "Io ho un po?"))
    )
    assert reformulation.keywords_it == [stub_llm.FALLBACK_KEYWORD]


async def test_answer_citations_are_exactly_the_evidence_ids_in_the_user_text(
    http: httpx2.AsyncClient,
) -> None:
    user = f"Domanda: {QUESTION}\n\n{format_evidence(EVIDENCE)}"
    draft = AnswerDraft.model_validate_json(await _text(http, _request(AnswerDraft, user)))
    assert draft.citations == [HANDBOOK_ID, OTHER_ID]
    assert draft.answer == "Secondo il manuale: Come richiedere le ferie"
    assert draft.grounded is True
    assert draft.confidence == pytest.approx(0.95)


async def test_answer_without_evidence_has_no_citation(http: httpx2.AsyncClient) -> None:
    draft = AnswerDraft.model_validate_json(
        await _text(http, _request(AnswerDraft, f"Domanda: {QUESTION}\n\n"))
    )
    assert draft.citations == []
    assert draft.answer == stub_llm.FALLBACK_ANSWER


async def test_an_unknown_schema_title_is_refused_with_400(http: httpx2.AsyncClient) -> None:
    class Unknown(BaseModel):
        value: int

    response = await http.post("/v1/messages", json=_request(Unknown, QUESTION))
    assert response.status_code == 400


@pytest.mark.parametrize(
    "body",
    [
        {"model": "m", "messages": [{"role": "user", "content": "x"}]},
        {"model": "m", "system": "no schema here", "messages": []},
        ["not", "an", "object"],
    ],
)
async def test_a_request_without_a_readable_schema_is_refused_with_400(
    http: httpx2.AsyncClient, body: object
) -> None:
    response = await http.post("/v1/messages", json=body)
    assert response.status_code == 400


async def test_a_body_that_is_not_json_is_refused_with_400(http: httpx2.AsyncClient) -> None:
    response = await http.post("/v1/messages", content=b"{", headers={"content-type": "text/plain"})
    assert response.status_code == 400


async def test_the_real_client_gets_a_valid_answer_draft_through_structured(
    http: httpx2.AsyncClient,
) -> None:
    anthropic = AsyncAnthropic(
        base_url="http://stub-llm:8090", api_key="meridian-local", http_client=http, max_retries=0
    )
    client = AnthropicMessagesClient(anthropic)
    draft = await client.structured(
        AnswerDraft,
        model="claude-test",
        system="Rispondi dalle fonti.",
        user=f"Domanda: {QUESTION}\n\n{format_evidence(EVIDENCE)}",
        max_tokens=100,
    )
    assert draft.citations == [HANDBOOK_ID, OTHER_ID]
    assert json.loads(draft.model_dump_json())["grounded"] is True


async def test_the_stub_never_logs_request_text(
    http: httpx2.AsyncClient, caplog: pytest.LogCaptureFixture
) -> None:
    secret_question = "Domanda riservata sul trasferimento di sede"
    with caplog.at_level(logging.DEBUG, logger="stub_llm"):
        await _text(http, _request(Reformulation, secret_question))
        await http.post("/v1/messages", json={"system": secret_question})
    assert caplog.records, "the stub logs counts and modes"
    assert "riservata" not in caplog.text
    assert "trasferimento" not in caplog.text
