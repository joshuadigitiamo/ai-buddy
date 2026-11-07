"""Anti-corruption layer: every Google Chat event shape becomes one ChatEvent.

Two shapes exist: the legacy flat one (`type` at top level) and the add-on one (a top-level `chat`
key, default for apps created after July 2025). Nothing past `normalize_event` reads a raw payload.
"""

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Final, Literal


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

_LifecycleKind = Literal["added", "removed"]
_ADDON_LIFECYCLE: Final[tuple[tuple[str, _LifecycleKind], ...]] = (
    ("addedToSpacePayload", "added"),
    ("removedFromSpacePayload", "removed"),
)
_LEGACY_LIFECYCLE: Final[dict[str, _LifecycleKind]] = {
    "ADDED_TO_SPACE": "added",
    "REMOVED_FROM_SPACE": "removed",
}


def _message_text(message: Mapping[str, Any]) -> str:
    """argumentText is the text without the @mention; else strip a leading `@word` from text."""
    argument_text = (_string(message.get("argumentText")) or "").strip()
    if argument_text:
        return argument_text
    return _LEADING_MENTION.sub("", (_string(message.get("text")) or "").strip(), count=1).strip()


def _command_id(value: object) -> str | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return str(value)
    return _string(value)


def _build(
    kind: Literal["message", "added", "removed", "command"],
    *,
    space: object,
    user: object,
    message: Mapping[str, Any] | None = None,
    command_id: str | None = None,
) -> ChatEvent | None:
    space_map = _mapping(space)
    space_name = _string(space_map.get("name"))
    if space_name is None:
        return None
    user_map = _mapping(user)
    message_map = message if message is not None else {}
    email = _string(user_map.get("email"))
    return ChatEvent(
        kind=kind,
        message_name=_string(message_map.get("name")),
        text=_message_text(message_map),
        space_name=space_name,
        is_dm=space_map.get("type") == "DM" or space_map.get("spaceType") == "DIRECT_MESSAGE",
        thread_name=_string(_mapping(message_map.get("thread")).get("name")),
        user_name=_string(user_map.get("name")),
        user_email=email.lower() if email else None,
        is_bot_sender=user_map.get("type") == "BOT",
        command_id=command_id,
    )


def _normalize_legacy(payload: Mapping[str, Any]) -> ChatEvent | None:
    event_type = payload.get("type")
    space, user = payload.get("space"), payload.get("user")
    if event_type == "MESSAGE":
        message = payload.get("message")
        if not isinstance(message, Mapping):
            return None
        if message.get("slashCommand") is None:
            return _build("message", space=space, user=user, message=message)
        command_id = _command_id(_mapping(message.get("slashCommand")).get("commandId"))
        if command_id is None:
            return None
        return _build("command", space=space, user=user, message=message, command_id=command_id)
    if isinstance(event_type, str) and event_type in _LEGACY_LIFECYCLE:
        return _build(_LEGACY_LIFECYCLE[event_type], space=space, user=user)
    return None


def _normalize_addon(chat: Mapping[str, Any]) -> ChatEvent | None:
    user = chat.get("user")
    message_payload = chat.get("messagePayload")
    if message_payload is not None:
        message = _mapping(message_payload).get("message")
        if not isinstance(message, Mapping):
            return None
        return _build(
            "message", space=_mapping(message_payload).get("space"), user=user, message=message
        )
    command_payload = chat.get("appCommandPayload")
    if command_payload is not None:
        payload = _mapping(command_payload)
        command_id = _command_id(_mapping(payload.get("appCommandMetadata")).get("appCommandId"))
        if command_id is None:
            return None
        message = payload.get("message")
        return _build(
            "command",
            space=payload.get("space"),
            user=user,
            message=message if isinstance(message, Mapping) else None,
            command_id=command_id,
        )
    for key, kind in _ADDON_LIFECYCLE:
        lifecycle = chat.get(key)
        if lifecycle is not None:
            return _build(kind, space=_mapping(lifecycle).get("space"), user=user)
    return None


def normalize_event(payload: object) -> ChatEvent | None:
    """Return a ChatEvent for a recognised event, None for anything else. Never raises."""
    if not isinstance(payload, Mapping):
        return None
    if "chat" in payload:
        chat = payload["chat"]
        return _normalize_addon(chat) if isinstance(chat, Mapping) else None
    return _normalize_legacy(payload)
