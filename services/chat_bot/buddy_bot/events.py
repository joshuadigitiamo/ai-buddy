"""Normalised Google Chat events. Tracer scope: the legacy flat MESSAGE event (03-04 completes)."""

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


def normalize_event(payload: Mapping[str, Any]) -> ChatEvent | None:
    """Return a ChatEvent for a legacy MESSAGE event, None for anything else."""
    if payload.get("type") != "MESSAGE":
        return None
    message = _mapping(payload.get("message"))
    space = _mapping(payload.get("space"))
    user = _mapping(payload.get("user"))
    space_name = _string(space.get("name"))
    if space_name is None:
        return None
    text = (_string(message.get("argumentText")) or "").strip()
    if not text:
        text = (_string(message.get("text")) or "").strip()
    is_dm = space.get("type") == "DM" or space.get("spaceType") == "DIRECT_MESSAGE"
    return ChatEvent(
        kind="message",
        message_name=_string(message.get("name")),
        text=text,
        space_name=space_name,
        is_dm=is_dm,
        thread_name=_string(_mapping(message.get("thread")).get("name")),
        user_name=_string(user.get("name")),
        user_email=_string(user.get("email")),
        is_bot_sender=user.get("type") == "BOT",
        command_id=None,
    )
