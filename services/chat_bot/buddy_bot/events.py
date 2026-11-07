"""Anti-corruption layer: every Google Chat event shape becomes one ChatEvent.

Two shapes exist: the legacy flat one (`type` at top level) and the add-on one (a top-level `chat`
key, default for apps created after July 2025). Nothing past `normalize_event` reads a raw payload.
"""

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal


@dataclass(frozen=True, slots=True)
class ChatEvent:
    """The fields the bot reads from an event; everything else is dropped on purpose."""

    kind: Literal["message", "added", "removed", "command"]
    message_name: str | None
    text: str
    space_name: str
    is_dm: bool
    thread_name: str | None
    user_name: str | None
    user_email: str | None
    is_bot_sender: bool
    command_id: str | None


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _string(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


_LEADING_MENTION = re.compile(r"^@\S+\s*")


def _message_text(message: Mapping[str, Any]) -> str:
    """argumentText is the text without the @mention; else strip a leading `@word` from text."""
    argument_text = (_string(message.get("argumentText")) or "").strip()
    if argument_text:
        return argument_text
    return _LEADING_MENTION.sub("", (_string(message.get("text")) or "").strip(), count=1).strip()


def _build_message(
    space: Mapping[str, Any], message: Mapping[str, Any], user: Mapping[str, Any]
) -> ChatEvent | None:
    space_name = _string(space.get("name"))
    if space_name is None:
        return None
    return ChatEvent(
        kind="message",
        message_name=_string(message.get("name")),
        text=_message_text(message),
        space_name=space_name,
        is_dm=space.get("type") == "DM" or space.get("spaceType") == "DIRECT_MESSAGE",
        thread_name=_string(_mapping(message.get("thread")).get("name")),
        user_name=_string(user.get("name")),
        user_email=_string(user.get("email")),
        is_bot_sender=user.get("type") == "BOT",
        command_id=None,
    )


def _normalize_legacy(payload: Mapping[str, Any]) -> ChatEvent | None:
    if payload.get("type") != "MESSAGE":
        return None
    return _build_message(
        _mapping(payload.get("space")),
        _mapping(payload.get("message")),
        _mapping(payload.get("user")),
    )


def _normalize_addon(chat: Mapping[str, Any]) -> ChatEvent | None:
    payload = _mapping(chat.get("messagePayload"))
    return _build_message(
        _mapping(payload.get("space")),
        _mapping(payload.get("message")),
        _mapping(chat.get("user")),
    )


def normalize_event(payload: object) -> ChatEvent | None:
    """Return a ChatEvent for a recognised event, None for anything else. Never raises."""
    if not isinstance(payload, Mapping):
        return None
    if "chat" in payload:
        return _normalize_addon(_mapping(payload["chat"]))
    return _normalize_legacy(payload)
