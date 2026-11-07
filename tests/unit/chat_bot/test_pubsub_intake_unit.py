"""BOT-01 offline: the Pub/Sub adapter's callback and run loop with fake message and subscriber."""

import asyncio
import json
import logging
import threading
from collections.abc import Callable, Mapping
from concurrent.futures import Future
from typing import Any

import pytest

from buddy_bot.intake.pubsub import PubSubIntake, make_callback

pytestmark = pytest.mark.anyio


class FakeMessage:
    def __init__(self, data: bytes) -> None:
        self.data = data
        self.acks = 0
        self.nacks = 0

    def ack(self) -> None:
        self.acks += 1

    def nack(self) -> None:
        self.nacks += 1


class FakeSubscriber:
    def __init__(self) -> None:
        self.future: Future[Any] = Future()
        self.path: str | None = None
        self.callback: Callable[[FakeMessage], None] | None = None
        self.max_messages: int | None = None
        self.closed = False
        self.cancelled = False
        self.future.add_done_callback(self._mark)

    def _mark(self, future: Future[Any]) -> None:
        self.cancelled = future.cancelled()

    def subscribe(
        self, path: str, *, callback: Callable[[FakeMessage], None], flow_control: Any
    ) -> Future[Any]:
        self.path = path
        self.callback = callback
        self.max_messages = flow_control.max_messages
        return self.future

    def close(self) -> None:
        self.closed = True


class Recorder:
    def __init__(self, fail: bool = False) -> None:
        self.events: list[Mapping[str, Any]] = []
        self.threads: list[str] = []
        self._fail = fail

    async def __call__(self, event: Mapping[str, Any]) -> None:
        self.events.append(event)
        self.threads.append(threading.current_thread().name)
        if self._fail:
            raise RuntimeError("secret detail")


async def _deliver(callback: Callable[[FakeMessage], None], message: FakeMessage) -> None:
    """Run the callback on a worker thread, as the subscriber library does."""
    await asyncio.to_thread(callback, message)


async def test_callback_runs_the_handler_on_the_loop_and_acks() -> None:
    handler = Recorder()
    callback = make_callback(handler, asyncio.get_running_loop())
    message = FakeMessage(json.dumps({"type": "MESSAGE"}).encode())

    await _deliver(callback, message)

    assert handler.events == [{"type": "MESSAGE"}]
    assert handler.threads == [threading.current_thread().name]
    assert message.acks == 1


@pytest.mark.parametrize("data", [b"not json", b"\xff\xfe", b"[1, 2]", b'"text"', b"42", b""])
async def test_undecodable_or_non_object_payload_is_acked_without_calling_the_handler(
    data: bytes, caplog: pytest.LogCaptureFixture
) -> None:
    handler = Recorder()
    callback = make_callback(handler, asyncio.get_running_loop())
    message = FakeMessage(data)

    with caplog.at_level(logging.DEBUG):
        await _deliver(callback, message)

    assert handler.events == []
    assert message.acks == 1
    assert "pubsub message ignored" in caplog.text


async def test_a_raising_handler_still_acks_and_logs_the_type_only(
    caplog: pytest.LogCaptureFixture,
) -> None:
    handler = Recorder(fail=True)
    callback = make_callback(handler, asyncio.get_running_loop())
    message = FakeMessage(b'{"k": "v"}')

    with caplog.at_level(logging.DEBUG):
        await _deliver(callback, message)

    assert message.acks == 1
    assert "RuntimeError" in caplog.text
    assert "secret detail" not in caplog.text


async def test_run_subscribes_with_flow_control_and_ends_when_the_stream_ends() -> None:
    subscriber = FakeSubscriber()
    intake = PubSubIntake("projects/p/subscriptions/s", subscriber_factory=lambda: subscriber)
    task = asyncio.create_task(intake.run(Recorder()))
    while subscriber.callback is None:
        await asyncio.sleep(0.01)

    assert subscriber.path == "projects/p/subscriptions/s"
    assert subscriber.max_messages == 2
    assert not task.done()

    subscriber.future.set_result(True)
    await asyncio.wait_for(task, timeout=2)

    assert subscriber.closed


async def test_cancelling_run_cancels_the_stream_and_closes_the_subscriber() -> None:
    subscriber = FakeSubscriber()
    intake = PubSubIntake(
        "projects/p/subscriptions/s",
        subscriber_factory=lambda: subscriber,
        max_messages=5,
    )
    task = asyncio.create_task(intake.run(Recorder()))
    while subscriber.callback is None:
        await asyncio.sleep(0.01)

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert subscriber.max_messages == 5
    assert subscriber.cancelled
    assert subscriber.closed


async def test_a_stream_failure_propagates_and_still_closes_the_subscriber() -> None:
    subscriber = FakeSubscriber()
    intake = PubSubIntake("projects/p/subscriptions/s", subscriber_factory=lambda: subscriber)
    task = asyncio.create_task(intake.run(Recorder()))
    while subscriber.callback is None:
        await asyncio.sleep(0.01)

    subscriber.future.set_exception(RuntimeError("stream broke"))
    with pytest.raises(RuntimeError, match="stream broke"):
        await task

    assert subscriber.closed


async def test_a_closed_loop_nacks_so_pubsub_redelivers(caplog: pytest.LogCaptureFixture) -> None:
    handler = Recorder()
    loop = asyncio.new_event_loop()
    loop.close()
    callback = make_callback(handler, loop)
    message = FakeMessage(b'{"k": "v"}')

    with caplog.at_level(logging.DEBUG):
        await _deliver(callback, message)

    assert handler.events == []
    assert (message.acks, message.nacks) == (0, 1)
    assert "pubsub handler not run" in caplog.text


async def test_a_run_cancelled_at_shutdown_nacks() -> None:
    async def cancelled_mid_run(event: Mapping[str, Any]) -> None:
        task = asyncio.current_task()
        assert task is not None
        task.cancel()
        await asyncio.sleep(30)

    callback = make_callback(cancelled_mid_run, asyncio.get_running_loop())
    message = FakeMessage(b'{"k": "v"}')

    await _deliver(callback, message)

    assert (message.acks, message.nacks) == (0, 1)


async def test_handled_and_undecodable_messages_are_never_nacked() -> None:
    callback = make_callback(Recorder(fail=True), asyncio.get_running_loop())
    handled, undecodable = FakeMessage(b'{"k": "v"}'), FakeMessage(b"not json")

    await _deliver(callback, handled)
    await _deliver(callback, undecodable)

    assert (handled.acks, handled.nacks) == (1, 0)
    assert (undecodable.acks, undecodable.nacks) == (1, 0)
