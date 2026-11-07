"""Allowlist: exact matching, missing senders and silent drops for every event kind (BOT-03)."""

import logging
from typing import Any

import pytest
from tests.unit.chat_bot.conftest import (
    GOOD_DRAFT,
    REFORMULATION,
    DictThreadMemory,
    FakeChatApi,
    FakeLlm,
    RecordingConnector,
    ServiceFactory,
    load_event,
)

from buddy_bot.schemas import AnswerDraft, Reformulation

pytestmark = pytest.mark.anyio


def _llm() -> FakeLlm:
    return FakeLlm({Reformulation: [REFORMULATION], AnswerDraft: [GOOD_DRAFT]})


def _with_user(event: dict[str, Any], user: dict[str, Any] | None) -> dict[str, Any]:
    changed = {**event}
    if "chat" in changed:
        changed["chat"] = {**changed["chat"]}
        target = changed["chat"]
    else:
        target = changed
    if user is None:
        target.pop("user", None)
    else:
        target["user"] = user
    return changed


async def _handled(
    make_service: ServiceFactory, event: dict[str, Any], allowed: frozenset[str]
) -> tuple[FakeChatApi, FakeLlm, DictThreadMemory]:
    chat, llm, memory = FakeChatApi(), _llm(), DictThreadMemory()
    service = make_service(llm, chat=chat, memory=memory, allowed_users=allowed)
    await service.handle(event)
    return chat, llm, memory


async def test_id_prefix_does_not_match(
    make_service: ServiceFactory, connector: RecordingConnector
) -> None:
    event = _with_user(load_event("legacy_dm_message"), {"name": "users/1234", "type": "HUMAN"})

    chat, llm, memory = await _handled(make_service, event, frozenset({"users/123"}))

    assert chat.created == [] and chat.updated == []
    assert llm.calls == [] and connector.calls == [] and memory.calls == 0


async def test_email_matches_regardless_of_case(make_service: ServiceFactory) -> None:
    event = _with_user(
        load_event("legacy_dm_message"),
        {"name": "users/999", "email": "Utente@Example.invalid", "type": "HUMAN"},
    )

    chat, _, _ = await _handled(make_service, event, frozenset({"utente@example.invalid"}))

    assert len(chat.created) == 1 and len(chat.updated) == 1


async def test_allowlist_entries_are_trimmed_and_lowercased(make_service: ServiceFactory) -> None:
    event = _with_user(
        load_event("legacy_dm_message"),
        {"name": "users/ABC", "type": "HUMAN"},
    )

    chat, _, _ = await _handled(make_service, event, frozenset({"  Users/abc "}))

    assert len(chat.updated) == 1


async def test_listed_email_admits_an_unlisted_name(make_service: ServiceFactory) -> None:
    event = _with_user(
        load_event("legacy_dm_message"),
        {"name": "users/not-listed", "email": "utente@example.invalid", "type": "HUMAN"},
    )

    chat, _, _ = await _handled(make_service, event, frozenset({"utente@example.invalid"}))

    assert len(chat.updated) == 1


@pytest.mark.parametrize("shape", ["legacy_dm_message", "addon_dm_message"])
async def test_event_without_sender_is_dropped(
    make_service: ServiceFactory, connector: RecordingConnector, shape: str
) -> None:
    event = _with_user(load_event(shape), None)

    chat, llm, memory = await _handled(make_service, event, frozenset({"users/111"}))

    assert chat.created == [] and chat.updated == []
    assert llm.calls == [] and connector.calls == [] and memory.calls == 0


async def test_sender_with_neither_name_nor_email_is_dropped(
    make_service: ServiceFactory, connector: RecordingConnector
) -> None:
    event = _with_user(load_event("legacy_dm_message"), {"type": "HUMAN", "displayName": "X"})

    chat, llm, memory = await _handled(make_service, event, frozenset({"users/111"}))

    assert chat.created == [] and chat.updated == []
    assert llm.calls == [] and connector.calls == [] and memory.calls == 0


@pytest.mark.parametrize(
    "shape",
    [
        "legacy_dm_message",
        "addon_room_mention",
        "legacy_added_to_space",
        "addon_added_to_space",
        "legacy_slash_command",
        "addon_app_command",
    ],
)
async def test_stranger_gets_no_call_for_any_event_kind(
    make_service: ServiceFactory, connector: RecordingConnector, shape: str
) -> None:
    stranger = {"name": "users/999", "email": "altro@example.invalid", "type": "HUMAN"}
    event = _with_user(load_event(shape), stranger)

    chat, llm, memory = await _handled(make_service, event, frozenset({"users/111"}))

    assert chat.created == [] and chat.updated == []
    assert llm.calls == [] and connector.calls == [] and memory.calls == 0


async def test_drop_log_carries_no_identity(
    make_service: ServiceFactory, caplog: pytest.LogCaptureFixture
) -> None:
    stranger = {"name": "users/999", "email": "altro@example.invalid", "displayName": "Mario"}
    event = _with_user(load_event("legacy_dm_message"), stranger)

    with caplog.at_level(logging.DEBUG):
        await _handled(make_service, event, frozenset({"users/111"}))

    assert caplog.records
    text = caplog.text
    assert "users/" not in text and "@" not in text and "Mario" not in text
