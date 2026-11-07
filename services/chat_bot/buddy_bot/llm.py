"""One Anthropic Messages client for every backend (Strategy behind the LlmClient port).

``LLM_BACKEND`` only changes the base URL and the key the same client uses (BOT-07). Structured
output is JSON in the prompt validated by pydantic: Meridian's native schema support is not
documented, so no provider feature is needed. No sampling parameters are sent (Meridian ignores
them and this anthropic version does not accept them).
"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING

from anthropic import APIError, AsyncAnthropic
from anthropic.types import TextBlock
from pydantic import ValidationError

from buddy_bot.config import BotSettings
from buddy_bot.ports import LlmOutputError, LlmUnavailableError, M

if TYPE_CHECKING:
    import httpx2

MERIDIAN_PLACEHOLDER_KEY = "meridian-local"

_FENCE = re.compile(r"```[A-Za-z0-9_-]*\s*(.*?)```", re.DOTALL)


def extract_json(text: str) -> str:
    """Return the JSON object inside ``text``: fence content if any, else first "{" to last "}"."""
    fenced = _FENCE.search(text)
    body = fenced.group(1) if fenced else text
    start, end = body.find("{"), body.rfind("}")
    if start == -1 or end < start:
        return body.strip()
    return body[start : end + 1]


def _json_instruction(schema: type[M]) -> str:
    return (
        "Rispondi con un solo oggetto JSON conforme a questo JSON schema, senza altro testo:\n"
        f"{json.dumps(schema.model_json_schema(), ensure_ascii=False)}"
    )


def _repair_note(error: ValidationError) -> str:
    """Name where and why the output failed, never what it said (it may echo user text)."""
    problems = "; ".join(
        f"{'.'.join(str(part) for part in err['loc']) or 'JSON'} ({err['type']})"
        for err in error.errors()
    )
    return (
        "La risposta precedente non era valida. Rispondi di nuovo con un solo oggetto JSON "
        f"conforme allo schema. Errori: {problems}."
    )


class AnthropicMessagesClient:
    """Implements the LlmClient port over one AsyncAnthropic; keeps no per-call state."""

    def __init__(self, client: AsyncAnthropic) -> None:
        self._client = client

    async def structured(
        self, schema: type[M], *, model: str, system: str, user: str, max_tokens: int
    ) -> M:
        full_system = f"{system}\n\n{_json_instruction(schema)}"
        text = await self._complete(model, full_system, user, max_tokens)
        try:
            return schema.model_validate_json(extract_json(text))
        except ValidationError as first:
            repair_user = f"{user}\n\n{_repair_note(first)}"
        # One repair, capped (each retry costs a full model call).
        text = await self._complete(model, full_system, repair_user, max_tokens)
        try:
            return schema.model_validate_json(extract_json(text))
        except ValidationError:
            # `from None`: the chained error would carry the model output into tracebacks.
            raise LlmOutputError(f"{schema.__name__} output invalid after one repair") from None

    async def _complete(self, model: str, system: str, user: str, max_tokens: int) -> str:
        try:
            response = await self._client.messages.create(
                model=model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
        except APIError as exc:
            # Type name only: the message may carry a host name or a response body.
            raise LlmUnavailableError(type(exc).__name__) from None
        return "".join(block.text for block in response.content if isinstance(block, TextBlock))


def build_llm_client(
    settings: BotSettings, *, http_client: httpx2.AsyncClient | None = None
) -> AnthropicMessagesClient:
    """Pick base URL and key from ``LLM_BACKEND``; ``http_client`` is injectable for tests."""
    if settings.llm_backend == "api":
        key = settings.anthropic_api_key
        assert key is not None  # BotSettings refuses api without ANTHROPIC_API_KEY
        client = AsyncAnthropic(
            api_key=key.get_secret_value(),
            timeout=settings.llm_timeout_seconds,
            max_retries=2,
            http_client=http_client,
        )
    elif settings.llm_backend == "meridian":
        meridian_key = settings.meridian_api_key
        client = AsyncAnthropic(
            base_url=settings.llm_base_url,
            api_key=meridian_key.get_secret_value() if meridian_key else MERIDIAN_PLACEHOLDER_KEY,
            timeout=settings.llm_timeout_seconds,
            max_retries=1,
            http_client=http_client,
        )
    else:
        raise ValueError("LLM_BACKEND=vertex is not enabled")
    return AnthropicMessagesClient(client)
