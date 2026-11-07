"""Pub/Sub streaming-pull intake (BOT-01): the development transport.

The subscriber library calls the callback on its own worker threads; the callback hands each
decoded event to the bot's event loop and blocks until the handler returns, so the lease keeps
being extended while a slow run is in flight. Every message is acked afterwards, undecodable ones
included, so a poison message cannot loop (the service's `handle` never raises). Log lines carry
fixed text and exception type names only, never message content (BOT-11).
"""

import asyncio
import json
import logging
from collections.abc import Callable
from typing import Any, Protocol

from google.cloud.pubsub_v1 import SubscriberClient, types

from buddy_bot.ports import EventHandler

_LOGGER = logging.getLogger("buddy_bot")

DEFAULT_MAX_MESSAGES = 2


class PubSubMessage(Protocol):
    """The part of a received Pub/Sub message the callback uses."""

    @property
    def data(self) -> bytes: ...

    def ack(self) -> None: ...


def make_callback(
    handler: EventHandler, loop: asyncio.AbstractEventLoop
) -> Callable[[PubSubMessage], None]:
    """Build the subscriber callback: decode, run `handler` on `loop`, always ack."""

    def callback(message: PubSubMessage) -> None:
        try:
            _dispatch(message, handler, loop)
        finally:
            message.ack()

    return callback


def _dispatch(
    message: PubSubMessage, handler: EventHandler, loop: asyncio.AbstractEventLoop
) -> None:
    try:
        event: Any = json.loads(message.data)
    except ValueError as exc:
        _LOGGER.warning("pubsub message ignored: %s", type(exc).__name__)
        return
    if not isinstance(event, dict):
        _LOGGER.warning("pubsub message ignored: not an object")
        return

    async def run_handler() -> None:
        await handler(event)

    try:
        asyncio.run_coroutine_threadsafe(run_handler(), loop).result()
    except Exception as exc:
        _LOGGER.error("pubsub handler failed: %s", type(exc).__name__)


class PubSubIntake:
    """IntakePort over a Pub/Sub subscription; `run` returns when the stream ends."""

    def __init__(
        self,
        subscription: str,
        *,
        subscriber_factory: Callable[[], SubscriberClient] = SubscriberClient,
        max_messages: int = DEFAULT_MAX_MESSAGES,
    ) -> None:
        self._subscription = subscription
        self._subscriber_factory = subscriber_factory
        self._max_messages = max_messages

    async def run(self, handler: EventHandler) -> None:
        loop = asyncio.get_running_loop()
        subscriber = self._subscriber_factory()
        future = subscriber.subscribe(
            self._subscription,
            callback=make_callback(handler, loop),
            flow_control=types.FlowControl(max_messages=self._max_messages),
        )
        try:
            await asyncio.wrap_future(future)
        finally:
            future.cancel()
            subscriber.close()
