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
VIDEO_CARD_ID: Final = "video-sources"
VIDEO_CARD_TITLE: Final = "Video della guida"
MAX_ANSWER_CHARS: Final = 3500
MAX_MESSAGE_CHARS: Final = 4000
MAX_VIDEO_SECTIONS: Final = 3

# The prompt forbids URLs in the answer; any the model wrote anyway is removed here.
_URL_TOKEN: Final = re.compile(r"(?:https?|handbook)://\S+", re.IGNORECASE)
_SPACE_RUN: Final = re.compile(r"[ \t]{2,}")
_WEB_SCHEMES: Final = ("http://", "https://")


def sanitize_prose(text: str) -> str:
    """Strip model-written links and neutralise angle brackets so it cannot form Chat markup."""
    without_links = _URL_TOKEN.sub("", text)
    neutral = without_links.replace("<", "‹").replace(">", "›")
    return _SPACE_RUN.sub(" ", neutral).strip()


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


def _link_button(text: str, url: str) -> dict[str, Any]:
    return {"text": text, "onClick": {"openLink": {"url": url}}}


def _video_section(source: Evidence, video_url: str, thumbnail_url: str | None) -> dict[str, Any]:
    widgets: list[dict[str, Any]] = []
    if thumbnail_url:
        alt_text = f"Anteprima del video: {source.title}"
        widgets.append({"image": {"imageUrl": thumbnail_url, "altText": alt_text}})
    widgets.append({"textParagraph": {"text": f"Indicizzata il {_date(source.revision_date)}"}})
    widgets.append(
        {
            "buttonList": {
                "buttons": [
                    _link_button("Fonte", source.source_url),
                    _link_button("Guarda", video_url),
                ]
            }
        }
    )
    return {"header": source.title, "widgets": widgets}


def _video_card(sources: list[Evidence], thumbnail_url: str | None) -> list[dict[str, Any]]:
    """One card, one section per cited Guides source that has a mapped video (D15, BOT-09)."""
    videos = [
        (source, source.video_url)
        for source in sources
        if source.kind == "guides"
        and source.video_url
        and source.video_url.lower().startswith(_WEB_SCHEMES)
    ][:MAX_VIDEO_SECTIONS]
    if not videos:
        return []
    sections = [_video_section(source, url, thumbnail_url) for source, url in videos]
    header = {"title": VIDEO_CARD_TITLE, "subtitle": videos[0][0].title}
    return [{"cardId": VIDEO_CARD_ID, "card": {"header": header, "sections": sections}}]


def _unique(sources: list[Evidence]) -> list[Evidence]:
    """Each source once, in order of first appearance (BOT-05)."""
    seen: set[str] = set()
    unique: list[Evidence] = []
    for source in sources:
        if source.source_url not in seen:
            seen.add(source.source_url)
            unique.append(source)
    return unique


def _contact_line(reply: BotReply) -> str | None:
    referente = reply.referente
    if referente is None or referente.contact_source is None:
        return None
    source = referente.contact_source
    return f"Contatto dal manuale: {source.title} ({source.source_url})"


def _referral_sentence(reply: BotReply) -> str:
    return f"Per il tuo caso specifico chiedi a {_role_text(reply)}."


def _cap_prose(prose: str) -> str:
    if len(prose) <= MAX_ANSWER_CHARS:
        return prose
    return prose[: MAX_ANSWER_CHARS - 1].rstrip() + "…"


# Chat renders standard Markdown: a lone newline is a soft break, so every line is its own
# paragraph (live check 2026-11-07: two Fonte lines ran together).
PARAGRAPH_BREAK: Final = "\n\n"


def _compose(prose: str, fonte_lines: list[str], tail: list[str]) -> str:
    """Join the blocks; whole Fonte lines are dropped from the end until the message fits."""
    kept = list(fonte_lines)
    while True:
        text = PARAGRAPH_BREAK.join(block for block in (prose, *kept, *tail) if block)
        if len(text) <= MAX_MESSAGE_CHARS or not kept:
            return text
        kept.pop()


def _clamp(text: str) -> str:
    if len(text) <= MAX_MESSAGE_CHARS:
        return text
    return text[: MAX_MESSAGE_CHARS - 1] + "…"


def _render_text(reply: BotReply) -> str:
    contact_line = _contact_line(reply)
    if reply.kind == "answer":
        tail = [line for line in (contact_line,) if line]
        if reply.referente is not None:
            tail.append(_referral_sentence(reply))
        lines = [_source_line(source) for source in _unique(reply.sources)]
        return _compose(_cap_prose(sanitize_prose(reply.answer)), lines, tail)
    if reply.kind == "refusal":
        head = f"Non lo so, chiedi a {_role_text(reply)}."
    elif reply.kind == "referral":
        head = _referral_sentence(reply)
    elif reply.kind == "smalltalk":
        return SMALLTALK_TEXT
    else:
        return ERROR_TEXT
    return PARAGRAPH_BREAK.join(line for line in (head, contact_line) if line)


def render_reply(reply: BotReply, *, video_thumbnail_url: str | None) -> RenderedMessage:
    """Render a reply; `video_thumbnail_url` is the static image shown on video cards."""
    cards: list[dict[str, Any]] = []
    if reply.kind == "answer":
        cards = _video_card(_unique(reply.sources), video_thumbnail_url)
    return RenderedMessage(text=_clamp(_render_text(reply)), cards_v2=cards)
