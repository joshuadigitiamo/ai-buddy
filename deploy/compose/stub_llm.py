"""Anthropic Messages-compatible stub LLM for the hermetic compose round trip (INFRA-02).

The chat bot's real client (buddy_bot.llm) posts to ``/v1/messages`` with the output schema
appended to ``system`` and expects one text block holding a JSON object. This stub reads the
schema title and answers each workflow step with a deterministic object, so the full path
(intake, retrieval over the MCP server, gate, render) runs without a model or a Max session.

It logs counts only, never request text (BOT-11 posture): employee questions never reach a log.
"""

from __future__ import annotations

import itertools
import json
import logging
import re
from typing import Any, Final

import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

INSTRUCTION: Final = (
    "Rispondi con un solo oggetto JSON conforme a questo JSON schema, senza altro testo:\n"
)
PORT: Final = 8090
MAX_KEYWORDS: Final = 5
FALLBACK_KEYWORD: Final = "manuale"
FALLBACK_ANSWER: Final = "Secondo il manuale, la risposta è nella fonte citata."
_MAX_SENTENCE_CHARS: Final = 200

_WORD = re.compile(r"[^\W\d_]{4,}")
_FONTE_ID = re.compile(r'<fonte id="([^"]+)"')
_FONTE_BODY = re.compile(r'<fonte id="[^"]*" tipo="[^"]*" titolo="[^"]*">(.*?)</fonte>', re.DOTALL)

_LOGGER = logging.getLogger("stub_llm")
_counter = itertools.count(1)


def _schema_title(system: str) -> str | None:
    """The ``title`` of the JSON schema that follows the bot's fixed instruction text."""
    _, marker, tail = system.rpartition(INSTRUCTION)
    if not marker:
        return None
    try:
        schema = json.loads(tail)
    except ValueError:
        return None
    title = schema.get("title") if isinstance(schema, dict) else None
    return title if isinstance(title, str) else None


def _last_line(text: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return lines[-1] if lines else ""


def _keywords(text: str) -> list[str]:
    """Up to five distinct words of four or more letters; a fixed word when there is none."""
    words = list(dict.fromkeys(word.lower() for word in _WORD.findall(text)))
    return words[:MAX_KEYWORDS] or [FALLBACK_KEYWORD]


def _first_sentence(user: str) -> str:
    """First sentence of the first evidence block, skipping header and markup lines."""
    block = _FONTE_BODY.search(user)
    if block is None:
        return FALLBACK_ANSWER
    for raw in block.group(1).splitlines():
        line = raw.strip()
        if not line or line.startswith(("Fonte:", "#", "!", "<", "---")):
            continue
        sentence = line.split(". ", 1)[0].strip()
        return f"Secondo il manuale: {sentence[:_MAX_SENTENCE_CHARS]}"
    return FALLBACK_ANSWER


def _citations(user: str) -> list[str]:
    """Every evidence id present in the user text, in order, each once."""
    return list(dict.fromkeys(_FONTE_ID.findall(user)))


def _payload(title: str, user: str) -> dict[str, Any] | None:
    if title == "Reformulation":
        words = _keywords(_last_line(user))
        return {
            "standalone_question": _last_line(user) or FALLBACK_KEYWORD,
            "keywords_it": words,
            "keywords_en": words,
            "intent": "question",
            "sensitive_topic": None,
        }
    if title == "RetryPlan":
        words = _keywords(_last_line(user))
        return {"keywords_it": words, "keywords_en": words}
    if title == "ContactExtraction":
        return {"contact": None, "source_url": None}
    if title == "AnswerDraft":
        return {
            "answer": _first_sentence(user),
            "citations": _citations(user),
            "grounded": True,
            "confidence": 0.95,
        }
    return None


def _user_text(body: dict[str, Any]) -> str:
    messages = body.get("messages")
    if not isinstance(messages, list) or not messages or not isinstance(messages[0], dict):
        return ""
    content = messages[0].get("content")
    return content if isinstance(content, str) else ""


async def messages(request: Request) -> JSONResponse:
    try:
        body = await request.json()
    except ValueError:
        return JSONResponse({"error": "invalid json"}, status_code=400)
    if not isinstance(body, dict):
        return JSONResponse({"error": "invalid body"}, status_code=400)
    system = body.get("system")
    title = _schema_title(system) if isinstance(system, str) else None
    payload = _payload(title, _user_text(body)) if title else None
    if payload is None:
        _LOGGER.warning("stub llm: unknown schema, request refused")
        return JSONResponse({"error": "unknown schema"}, status_code=400)
    number = next(_counter)
    _LOGGER.info("stub llm: request %d answered as %s", number, title)
    return JSONResponse(
        {
            "id": f"msg_stub_{number}",
            "type": "message",
            "role": "assistant",
            "model": str(body.get("model", "stub")),
            "content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False)}],
            "stop_reason": "end_turn",
            "stop_sequence": None,
            "usage": {"input_tokens": 0, "output_tokens": 0},
        }
    )


app = Starlette(routes=[Route("/v1/messages", messages, methods=["POST"])])


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    uvicorn.run(app, host="0.0.0.0", port=PORT, access_log=False, log_level="warning")
