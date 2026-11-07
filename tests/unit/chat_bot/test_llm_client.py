"""The Anthropic Messages client behind the LlmClient port, over a mock HTTP transport."""

import json
from collections.abc import Callable
from typing import Any

import httpx2
import pytest

from buddy_bot.config import BotSettings
from buddy_bot.llm import build_llm_client
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
