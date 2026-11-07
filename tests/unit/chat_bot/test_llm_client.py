"""The Anthropic Messages client behind the LlmClient port, over a mock HTTP transport."""

import asyncio
import json
from collections.abc import Callable
from typing import Any

import httpx2
import pytest
from anthropic import AsyncAnthropic

from buddy_bot.config import BotSettings
from buddy_bot.llm import MERIDIAN_PLACEHOLDER_KEY, AnthropicMessagesClient, build_llm_client
from buddy_bot.ports import LlmOutputError, LlmUnavailableError
from buddy_bot.schemas import Reformulation

pytestmark = pytest.mark.anyio

_ENV_VARIABLES = (
    "ALLOWED_USERS",
    "LLM_BACKEND",
    "LLM_BASE_URL",
    "ANTHROPIC_API_KEY",
    "MERIDIAN_API_KEY",
    "VERTEX_PROJECT",
    "VERTEX_REGION",
    "REFORMULATE_MODEL",
    "ANSWER_MODEL",
    "LLM_TIMEOUT_SECONDS",
    "CONFIDENCE_THRESHOLD",
    "MEMORY_TURNS",
    "THREAD_KEY_SECRET",
    "MEMORY_COLLECTION",
    "GOOGLE_CLOUD_PROJECT",
    "MCP_URL",
    "MCP_AUTH",
    "MCP_AUDIENCE",
    "INTAKE",
    "PUBSUB_SUBSCRIPTION",
    "CHAT_JWT_AUDIENCE",
    "CHAT_JWT_ISSUER_EMAIL",
    "BOT_HOST",
    "PORT",
    "VIDEO_THUMBNAIL_URL",
    "HELP_COMMAND_ID",
    "RUN_DEADLINE_SECONDS",
    "LANGSMITH_TRACING",
    "LANGCHAIN_TRACING_V2",
    "K_SERVICE",
)

FAKE_API_KEY = "sk-test-fake"
VALID_REFORMULATION = {
    "standalone_question": "Quanti giorni di ferie spettano?",
    "keywords_it": ["ferie", "giorni"],
    "keywords_en": ["leave", "days"],
    "intent": "question",
    "sensitive_topic": None,
}


@pytest.fixture(autouse=True)
def _clean_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """run-unit-tests.sh loads an env file into the container; start from nothing."""
    for name in _ENV_VARIABLES:
        monkeypatch.delenv(name, raising=False)


def settings_env(monkeypatch: pytest.MonkeyPatch, **overrides: str | None) -> None:
    """Set a valid api-backend environment; an override of None removes the variable."""
    values: dict[str, str | None] = {
        "ALLOWED_USERS": "users/111111111111111111111",
        "LLM_BACKEND": "api",
        "ANTHROPIC_API_KEY": FAKE_API_KEY,
        "THREAD_KEY_SECRET": "s" * 40,
        "MCP_URL": "http://mcp.invalid/mcp",
        "MCP_AUTH": "none",
        "INTAKE": "pubsub",
        "PUBSUB_SUBSCRIPTION": "projects/demo-ai-buddy/subscriptions/chat",
        "VIDEO_THUMBNAIL_URL": "https://example.invalid/thumb.png",
    }
    values.update(overrides)
    for name, value in values.items():
        if value is None:
            monkeypatch.delenv(name, raising=False)
        else:
            monkeypatch.setenv(name, value)


def messages_response(text: str) -> httpx2.Response:
    """A Messages API response whose single text block holds ``text``."""
    return httpx2.Response(
        200,
        json={
            "id": "msg_test",
            "type": "message",
            "role": "assistant",
            "model": "claude-test",
            "content": [{"type": "text", "text": text}],
            "stop_reason": "end_turn",
            "stop_sequence": None,
            "usage": {"input_tokens": 1, "output_tokens": 1},
        },
    )


def mock_http(
    handler: Callable[[httpx2.Request], httpx2.Response],
) -> tuple[httpx2.AsyncClient, list[httpx2.Request]]:
    """An httpx2 client over a mock transport, plus the list that records every request."""
    seen: list[httpx2.Request] = []

    def record(request: httpx2.Request) -> httpx2.Response:
        seen.append(request)
        return handler(request)

    return httpx2.AsyncClient(transport=httpx2.MockTransport(record)), seen


# anthropic 2.6.0 sends api_key as "Authorization: Bearer <key>"; it no longer sets "x-api-key".
def request_body(request: httpx2.Request) -> dict[str, Any]:
    body: dict[str, Any] = json.loads(request.content)
    return body


async def test_api_backend_returns_validated_reformulation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings_env(monkeypatch)
    http, seen = mock_http(lambda _r: messages_response(json.dumps(VALID_REFORMULATION)))
    settings = BotSettings()
    llm = build_llm_client(settings, http_client=http)

    result = await llm.structured(
        Reformulation,
        model=settings.reformulate_model,
        system="Riformula la domanda.",
        user="Quanti giorni di ferie ho?",
        max_tokens=300,
    )

    assert isinstance(result, Reformulation)
    assert result.standalone_question == VALID_REFORMULATION["standalone_question"]
    assert result.keywords_it == ["ferie", "giorni"]
    assert result.intent == "question"
    assert len(seen) == 1
    assert seen[0].url.path == "/v1/messages"
    assert seen[0].headers["authorization"] == f"Bearer {FAKE_API_KEY}"
    body = request_body(seen[0])
    assert body["model"] == "claude-haiku-5-5"
    assert not {"temperature", "top_p", "top_k"} & body.keys()
    assert "standalone_question" in body["system"]


def direct_client(handler: Callable[[httpx2.Request], httpx2.Response]) -> tuple[Any, list[Any]]:
    """An AnthropicMessagesClient with retries off, so error tests do not wait on backoff."""
    http, seen = mock_http(handler)
    sdk = AsyncAnthropic(api_key=FAKE_API_KEY, http_client=http, max_retries=0)
    return AnthropicMessagesClient(sdk), seen


async def ask(llm: Any) -> Reformulation:
    result: Reformulation = await llm.structured(
        Reformulation,
        model="claude-haiku-5-5",
        system="Riformula.",
        user="Domanda?",
        max_tokens=300,
    )
    return result


async def test_meridian_uses_the_same_client_with_placeholder_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings_env(monkeypatch, LLM_BACKEND="meridian", LLM_BASE_URL="http://meridian:3456")
    http, seen = mock_http(lambda _r: messages_response(json.dumps(VALID_REFORMULATION)))
    llm = build_llm_client(BotSettings(), http_client=http)

    await ask(llm)

    assert type(llm) is AnthropicMessagesClient
    assert str(seen[0].url) == "http://meridian:3456/v1/messages"
    assert seen[0].headers["authorization"] == f"Bearer {MERIDIAN_PLACEHOLDER_KEY}"


async def test_meridian_sends_the_configured_key(monkeypatch: pytest.MonkeyPatch) -> None:
    settings_env(
        monkeypatch,
        LLM_BACKEND="meridian",
        LLM_BASE_URL="http://meridian:3456",
        MERIDIAN_API_KEY="chiave-meridian-finta",
    )
    http, seen = mock_http(lambda _r: messages_response(json.dumps(VALID_REFORMULATION)))

    await ask(build_llm_client(BotSettings(), http_client=http))

    assert seen[0].headers["authorization"] == "Bearer chiave-meridian-finta"


async def test_json_wrapped_in_prose_and_code_fence_parses() -> None:
    wrapped = f"Ecco il JSON:\n```json\n{json.dumps(VALID_REFORMULATION)}\n```\nSpero sia utile."
    llm, seen = direct_client(lambda _r: messages_response(wrapped))

    result = await ask(llm)

    assert result.standalone_question == VALID_REFORMULATION["standalone_question"]
    assert len(seen) == 1


async def test_missing_field_is_repaired_once_with_locations_only() -> None:
    first = json.dumps({"standalone_question": "SENTINELLA-PRIMO-OUTPUT"})
    replies = iter([first, json.dumps(VALID_REFORMULATION)])
    llm, seen = direct_client(lambda _r: messages_response(next(replies)))

    result = await ask(llm)

    assert result.keywords_it == ["ferie", "giorni"]
    assert len(seen) == 2
    repair_user = request_body(seen[1])["messages"][0]["content"]
    assert repair_user.startswith("Domanda?")
    assert "keywords_it" in repair_user
    assert "missing" in repair_user
    assert "SENTINELLA-PRIMO-OUTPUT" not in repair_user


async def test_unparseable_output_is_repaired_once_without_echoing_it() -> None:
    replies = iter(["SENTINELLA-PRIMO-OUTPUT non e json", json.dumps(VALID_REFORMULATION)])
    llm, seen = direct_client(lambda _r: messages_response(next(replies)))

    await ask(llm)

    assert len(seen) == 2
    assert "SENTINELLA-PRIMO-OUTPUT" not in request_body(seen[1])["messages"][0]["content"]


async def test_two_invalid_outputs_raise_output_error_after_exactly_two_requests() -> None:
    llm, seen = direct_client(lambda _r: messages_response('{"standalone_question": "SENTINELLA"}'))

    with pytest.raises(LlmOutputError) as caught:
        await ask(llm)

    assert len(seen) == 2
    assert "SENTINELLA" not in str(caught.value)
    assert "Reformulation" in str(caught.value)


async def test_connect_error_raises_unavailable_with_exception_type_only() -> None:
    def refuse(_request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ConnectError("SENTINELLA-host-interno:3456 irraggiungibile")

    llm, _seen = direct_client(refuse)

    with pytest.raises(LlmUnavailableError) as caught:
        await ask(llm)

    assert str(caught.value) == "APIConnectionError"


async def test_timeout_raises_unavailable() -> None:
    def too_slow(_request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ReadTimeout("SENTINELLA letto troppo lentamente")

    llm, _seen = direct_client(too_slow)

    with pytest.raises(LlmUnavailableError) as caught:
        await ask(llm)

    assert str(caught.value) == "APITimeoutError"


async def test_http_error_status_raises_unavailable() -> None:
    llm, _seen = direct_client(lambda _r: httpx2.Response(500, json={"error": "SENTINELLA"}))

    with pytest.raises(LlmUnavailableError) as caught:
        await ask(llm)

    assert "SENTINELLA" not in str(caught.value)


def test_timeout_setting_reaches_the_client(monkeypatch: pytest.MonkeyPatch) -> None:
    settings_env(monkeypatch, LLM_TIMEOUT_SECONDS="7")

    llm = build_llm_client(BotSettings())

    assert llm._client.timeout == 7


async def test_concurrent_calls_share_one_client_without_mixing_results() -> None:
    def echo(request: httpx2.Request) -> httpx2.Response:
        asked = request_body(request)["messages"][0]["content"]
        return messages_response(json.dumps({**VALID_REFORMULATION, "standalone_question": asked}))

    llm, seen = direct_client(echo)

    async def one(question: str) -> Reformulation:
        result: Reformulation = await llm.structured(
            Reformulation, model="m", system="s", user=question, max_tokens=300
        )
        return result

    first, second = await asyncio.gather(one("prima domanda"), one("seconda domanda"))

    assert (first.standalone_question, second.standalone_question) == (
        "prima domanda",
        "seconda domanda",
    )
    assert len(seen) == 2
