"""Turn a BotReply into Chat message text. Links come from Evidence, never from model text."""

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Final

from buddy_bot.schemas import BotReply, Evidence

SMALLTALK_TEXT: Final = (
    "Posso rispondere solo a domande sul manuale aziendale e sulle Guide tecniche. "
    "Prova a chiedermi qualcosa su questi temi."
)
ERROR_TEXT: Final = "Non riesco a rispondere in questo momento. Riprova tra poco."

# The prompt forbids URLs in the answer; any the model wrote anyway is removed here.
_URL_TOKEN: Final = re.compile(r"(?:https?|handbook)://\S+", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class RenderedMessage:
    text: str
    cards_v2: list[dict[str, Any]] = field(default_factory=list)


def _date(value: str) -> str:
    try:
        return datetime.fromisoformat(value).date().isoformat()
    except ValueError:
        return value[:10]


def _source_line(source: Evidence) -> str:
    day = _date(source.revision_date)
    if source.kind == "handbook":
        return f"Fonte: Manuale – {source.title} ({source.source_url}), revisione {day}"
    return f"Fonte: Guida – {source.title} ({source.source_url}), indicizzata il {day}"


def _role_text(reply: BotReply) -> str:
    referente = reply.referente
    role = referente.role if referente else "HR"
    if referente and referente.contact:
        return f"{role} ({referente.contact})"
    return role


def render_reply(reply: BotReply, *, video_thumbnail_url: str | None) -> RenderedMessage:
    """Render a reply; `video_thumbnail_url` is used by the card in 03-08."""
    if reply.kind == "answer":
        prose = _URL_TOKEN.sub("", reply.answer).strip()
        lines = [_source_line(source) for source in reply.sources]
        return RenderedMessage(text="\n\n".join([prose, "\n".join(lines)]) if lines else prose)
    if reply.kind == "refusal":
        return RenderedMessage(text=f"Non lo so, chiedi a {_role_text(reply)}.")
    if reply.kind == "referral":
        return RenderedMessage(text=f"Per il tuo caso specifico chiedi a {_role_text(reply)}.")
    if reply.kind == "smalltalk":
        return RenderedMessage(text=SMALLTALK_TEXT)
    return RenderedMessage(text=ERROR_TEXT)
