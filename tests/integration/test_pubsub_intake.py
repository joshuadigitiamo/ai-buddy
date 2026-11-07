"""BOT-01 end to end: a Chat event published on the Pub/Sub emulator reaches the bot."""

import asyncio
import contextlib
import os
import uuid
from collections.abc import Callable, Iterator

import pytest
from google.api_core.exceptions import DeadlineExceeded
from google.cloud.pubsub_v1 import PublisherClient, SubscriberClient
from tests.unit.chat_bot.conftest import (
    EVENTS_DIR,
    GOOD_DRAFT,
    REFORMULATION,
    DictThreadMemory,
    FakeChatApi,
    FakeLlm,
    ServiceFactory,
    connector,  # noqa: F401  (fixtures reused from the unit conftest)
    gaplog,  # noqa: F401
    make_service,  # noqa: F401
    mcp_server,  # noqa: F401
    workflow_config,  # noqa: F401
)

from buddy_bot.intake.pubsub import PubSubIntake
from buddy_bot.schemas import AnswerDraft, Reformulation

pytestmark = [
    pytest.mark.pubsub,
    pytest.mark.anyio,
    pytest.mark.skipif(
        not os.environ.get("PUBSUB_EMULATOR_HOST"),
        reason="needs the Pub/Sub emulator: run ./run-unit-tests.sh --emulator",
    ),
]

PROJECT = "demo-ai-buddy"
WAIT_SECONDS = 20.0
EMPTY_PULL_TIMEOUT_SECONDS = 3.0


class _Channel:
    """A fresh topic and subscription on the emulator, removed afterwards."""

    def __init__(self) -> None:
        suffix = uuid.uuid4().hex
        self.publisher = PublisherClient()
        self.subscriber = SubscriberClient()
        self.topic = f"projects/{PROJECT}/topics/chat-{suffix}"
        self.subscription = f"projects/{PROJECT}/subscriptions/chat-{suffix}"
        self.publisher.create_topic(name=self.topic)
        self.subscriber.create_subscription(name=self.subscription, topic=self.topic)

    def publish(self, data: bytes) -> None:
        self.publisher.publish(self.topic, data).result(timeout=10)

    def pull_count(self) -> int:
        try:
            response = self.subscriber.pull(
                request={"subscription": self.subscription, "max_messages": 1},
                timeout=EMPTY_PULL_TIMEOUT_SECONDS,
            )
        except DeadlineExceeded:
            return 0
        return len(response.received_messages)

    def close(self) -> None:
        self.subscriber.delete_subscription(request={"subscription": self.subscription})
        self.publisher.delete_topic(request={"topic": self.topic})
        self.subscriber.close()


@pytest.fixture
def channel() -> Iterator[_Channel]:
    created = _Channel()
    yield created
    created.close()


async def _cancel(task: "asyncio.Task[None]") -> None:
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task


async def _wait_until(condition: Callable[[], bool]) -> None:
    deadline = asyncio.get_running_loop().time() + WAIT_SECONDS
    while not condition():
        if asyncio.get_running_loop().time() > deadline:
            raise AssertionError("condition not reached within the wait window")
        await asyncio.sleep(0.1)


async def test_dm_event_gets_placeholder_then_answer_and_is_acked(
    channel: _Channel,
    make_service: ServiceFactory,  # noqa: F811
) -> None:
    chat = FakeChatApi()
    llm = FakeLlm({Reformulation: [REFORMULATION], AnswerDraft: [GOOD_DRAFT]})
    service = make_service(llm, chat=chat, memory=DictThreadMemory())
    task = asyncio.create_task(PubSubIntake(channel.subscription).run(service.handle))
    try:
        channel.publish((EVENTS_DIR / "legacy_dm_message.json").read_bytes())
        await _wait_until(lambda: len(chat.updated) == 1)
    finally:
        await _cancel(task)
    assert len(chat.created) == 1
    assert chat.updated[0].name.endswith("placeholder-1")
    assert chat.updated[0].name.startswith(chat.created[0].space)
    assert "handbook://02-ferie" in chat.updated[0].text
    assert channel.pull_count() == 0


async def test_undecodable_message_is_acked_and_makes_no_call(
    channel: _Channel,
    make_service: ServiceFactory,  # noqa: F811
) -> None:
    chat = FakeChatApi()
    service = make_service(FakeLlm({}), chat=chat)
    task = asyncio.create_task(PubSubIntake(channel.subscription).run(service.handle))
    try:
        channel.publish(b"not json")
        await asyncio.sleep(3)
    finally:
        await _cancel(task)
    assert chat.created == []
    assert chat.updated == []
    assert channel.pull_count() == 0
