"""Service rules: canned replies, bot senders, duplicates, deadline, never-raise (D-13, BOT-10)."""

import asyncio
import logging
from typing import Any

import pytest
from tests.unit.chat_bot.conftest import (
    ALLOWED,
    GOOD_DRAFT,
    REFORMULATION,
    DictThreadMemory,
    FakeChatApi,
    FakeLlm,
    RecordingConnector,
    ServiceFactory,
    load_event,
    with_message,
)

from buddy_bot.ports import M
from buddy_bot.render import ERROR_TEXT
from buddy_bot.schemas import AnswerDraft, Reformulation
from buddy_bot.service import INTRO_TEXT, USAGE_TEXT

pytestmark = pytest.mark.anyio


def _llm() -> FakeLlm:
    return FakeLlm({Reformulation: [REFORMULATION] * 3, AnswerDraft: [GOOD_DRAFT] * 3})


class _SlowLlm(FakeLlm):
    async def structured(
        self, schema: type[M], *, model: str, system: str, user: str, max_tokens: int
    ) -> M:
        await asyncio.sleep(5)
        return await super().structured(
            schema, model=model, system=system, user=user, max_tokens=max_tokens
        )


class _FailingChat(FakeChatApi):
    async def create_message(self, *, space: str, thread: str | None, text: str) -> str:
        raise RuntimeError("chat-secret-detail")


class _Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def _assert_untouched(
    llm: FakeLlm, connector: RecordingConnector, memory: DictThreadMemory
) -> None:
    assert llm.calls == [] and connector.calls == [] and memory.calls == 0


def test_canned_texts_name_the_bot_and_the_sources() -> None:
    assert "/aiuto" in INTRO_TEXT
    assert "AI Buddy" in INTRO_TEXT
    assert "Guide" in USAGE_TEXT and "manuale" in USAGE_TEXT
    assert "?" in USAGE_TEXT


@pytest.mark.parametrize("shape", ["legacy_added_to_space", "addon_added_to_space"])
async def test_added_to_space_gets_intro_without_model_calls(
    make_service: ServiceFactory, connector: RecordingConnector, shape: str
) -> None:
    llm, chat, memory = _llm(), FakeChatApi(), DictThreadMemory()

    await make_service(llm, chat=chat, memory=memory).handle(load_event(shape))

    assert [(m.space, m.text) for m in chat.created] == [("spaces/AAAAsyntheticRoom", INTRO_TEXT)]
    assert chat.updated == []
    _assert_untouched(llm, connector, memory)


@pytest.mark.parametrize("shape", ["legacy_slash_command", "addon_app_command"])
async def test_aiuto_command_gets_usage_text(
    make_service: ServiceFactory, connector: RecordingConnector, shape: str
) -> None:
    llm, chat, memory = _llm(), FakeChatApi(), DictThreadMemory()

    await make_service(llm, chat=chat, memory=memory, help_command_id="1").handle(load_event(shape))

    assert [m.text for m in chat.created] == [USAGE_TEXT]
    assert chat.updated == []
    _assert_untouched(llm, connector, memory)


@pytest.mark.parametrize("text", ["/aiuto", "/AIUTO ferie"])
async def test_typed_aiuto_gets_usage_text(
    make_service: ServiceFactory, connector: RecordingConnector, text: str
) -> None:
    llm, chat, memory = _llm(), FakeChatApi(), DictThreadMemory()
    event = with_message(load_event("legacy_dm_message"), text=text)

    await make_service(llm, chat=chat, memory=memory).handle(event)

    assert [m.text for m in chat.created] == [USAGE_TEXT]
    _assert_untouched(llm, connector, memory)


@pytest.mark.parametrize("text", ["", "   "])
async def test_message_with_only_the_mention_gets_usage_text(
    make_service: ServiceFactory, connector: RecordingConnector, text: str
) -> None:
    llm, chat, memory = _llm(), FakeChatApi(), DictThreadMemory()
    event = with_message(load_event("addon_room_mention"), text=text)
    event["chat"]["messagePayload"]["message"]["text"] = "@AIBuddy "

    await make_service(llm, chat=chat, memory=memory).handle(event)

    assert [m.text for m in chat.created] == [USAGE_TEXT]
    assert chat.updated == []
    _assert_untouched(llm, connector, memory)


async def test_removed_from_space_produces_no_call(
    make_service: ServiceFactory, connector: RecordingConnector
) -> None:
    llm, chat, memory = _llm(), FakeChatApi(), DictThreadMemory()
    service = make_service(llm, chat=chat, memory=memory)

    await service.handle(load_event("legacy_removed_from_space"))
    await service.handle(load_event("addon_removed_from_space"))

    assert chat.created == [] and chat.updated == []
    _assert_untouched(llm, connector, memory)


async def test_bot_sender_produces_no_call_even_when_allowlisted(
    make_service: ServiceFactory, connector: RecordingConnector
) -> None:
    llm, chat, memory = _llm(), FakeChatApi(), DictThreadMemory()
    service = make_service(
        llm, chat=chat, memory=memory, allowed_users=ALLOWED | {"users/222222222222222222222"}
    )

    await service.handle(load_event("legacy_bot_sender"))

    assert chat.created == [] and chat.updated == []
    _assert_untouched(llm, connector, memory)


async def test_redelivered_event_is_handled_once(make_service: ServiceFactory) -> None:
    llm, chat, memory = _llm(), FakeChatApi(), DictThreadMemory()
    service = make_service(llm, chat=chat, memory=memory)
    event = load_event("legacy_dm_message")

    await service.handle(event)
    await service.handle(event)

    assert len(chat.created) == 1 and len(chat.updated) == 1
    assert len([c for c in llm.calls if c.schema is Reformulation]) == 1
    assert len(memory.append_calls) == 1


async def test_event_without_message_name_has_no_idempotency_key(
    make_service: ServiceFactory,
) -> None:
    llm, chat = _llm(), FakeChatApi()
    service = make_service(llm, chat=chat)
    event: dict[str, Any] = load_event("legacy_dm_message")
    del event["message"]["name"]

    await service.handle(event)
    await service.handle(event)

    assert len(chat.created) == 2


async def test_same_message_name_is_handled_again_after_the_ttl(
    make_service: ServiceFactory,
) -> None:
    llm, chat, clock = _llm(), FakeChatApi(), _Clock()
    service = make_service(llm, chat=chat, clock=clock)
    event = load_event("legacy_dm_message")

    await service.handle(event)
    clock.now += 599
    await service.handle(event)
    assert len(chat.created) == 1
    clock.now += 2
    await service.handle(event)

    assert len(chat.created) == 2


async def test_dedupe_table_is_capped(make_service: ServiceFactory) -> None:
    llm, chat = FakeLlm({}), FakeChatApi()
    service = make_service(llm, chat=chat, clock=_Clock())
    base = load_event("legacy_slash_command")

    for n in range(1030):
        await service.handle(with_message(base, name=f"spaces/AAAAsyntheticDM/messages/c-{n}"))
    first_again = len(chat.created)
    await service.handle(with_message(base, name="spaces/AAAAsyntheticDM/messages/c-0"))

    assert len(chat.created) == first_again + 1


async def test_workflow_exception_patches_the_placeholder_with_the_error_text(
    make_service: ServiceFactory, caplog: pytest.LogCaptureFixture
) -> None:
    llm = FakeLlm({Reformulation: [RuntimeError("boom-detail")]})
    chat = FakeChatApi()

    with caplog.at_level(logging.DEBUG):
        await make_service(llm, chat=chat).handle(load_event("legacy_dm_message"))

    assert len(chat.created) == 1
    assert [u.text for u in chat.updated] == [ERROR_TEXT]
    assert "RuntimeError" in caplog.text and "boom-detail" not in caplog.text


async def test_run_past_the_deadline_patches_the_error_text(
    make_service: ServiceFactory, connector: RecordingConnector
) -> None:
    llm = _SlowLlm({Reformulation: [REFORMULATION], AnswerDraft: [GOOD_DRAFT]})
    chat, memory = FakeChatApi(), DictThreadMemory()

    await make_service(llm, chat=chat, memory=memory, run_deadline_seconds=0.05).handle(
        load_event("legacy_dm_message")
    )

    assert [u.text for u in chat.updated] == [ERROR_TEXT]
    assert memory.append_calls == []


async def test_failing_chat_create_returns_without_other_calls(
    make_service: ServiceFactory,
    connector: RecordingConnector,
    caplog: pytest.LogCaptureFixture,
) -> None:
    llm, memory = _llm(), DictThreadMemory()
    chat = _FailingChat()

    with caplog.at_level(logging.DEBUG):
        await make_service(llm, chat=chat, memory=memory).handle(load_event("legacy_dm_message"))

    assert chat.updated == []
    _assert_untouched(llm, connector, memory)
    assert "RuntimeError" in caplog.text and "chat-secret-detail" not in caplog.text


@pytest.mark.parametrize(
    ("failing", "logged"),
    [("fail_recent", "memory read failed: RuntimeError"), ("fail_append", "memory write failed")],
)
async def test_memory_failure_does_not_stop_the_reply(
    make_service: ServiceFactory, caplog: pytest.LogCaptureFixture, failing: str, logged: str
) -> None:
    llm, chat, memory = _llm(), FakeChatApi(), DictThreadMemory()
    setattr(memory, failing, True)

    with caplog.at_level(logging.DEBUG):
        await make_service(llm, chat=chat, memory=memory).handle(load_event("legacy_dm_message"))

    assert len(chat.updated) == 1
    assert GOOD_DRAFT.answer in chat.updated[0].text
    assert logged in caplog.text
    assert "RuntimeError" in caplog.text


async def test_room_message_without_thread_uses_no_memory(make_service: ServiceFactory) -> None:
    llm, chat, memory = _llm(), FakeChatApi(), DictThreadMemory()
    event: dict[str, Any] = load_event("addon_room_mention")
    del event["chat"]["messagePayload"]["message"]["thread"]

    await make_service(llm, chat=chat, memory=memory).handle(event)

    assert len(chat.updated) == 1
    assert memory.calls == 0
