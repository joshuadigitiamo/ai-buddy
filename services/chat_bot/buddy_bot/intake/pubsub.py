"""Pub/Sub streaming-pull intake (BOT-01): the development transport.

The subscriber library calls the callback on its own worker threads; the callback hands each
decoded event to the bot's event loop and blocks until the handler returns, so the lease keeps
being extended while a slow run is in flight. A message is acked once the handler ran, whatever
it raised, and when it is undecodable, so a poison message cannot loop (the service's `handle`
never raises). It is nacked when the handler could not run (loop closed, run cancelled at
shutdown), so Pub/Sub redelivers it after a restart. Log lines carry
fixed text and exception type names only, never message content (BOT-11).
"""

import asyncio
import json
import logging
from collections.abc import Callable
from concurrent.futures import CancelledError
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

    def nack(self) -> None: ...


def make_callback(
    handler: EventHandler, loop: asyncio.AbstractEventLoop
) -> Callable[[PubSubMessage], None]:
    """Build the subscriber callback: decode, run `handler` on `loop`, ack (or nack, see above)."""

    def callback(message: PubSubMessage) -> None:
        try:
            delivered = _dispatch(message, handler, loop)
        except BaseException:
            message.nack()
            raise
        if delivered:
            message.ack()
        else:
            message.nack()

    return callback


def _dispatch(
    message: PubSubMessage, handler: EventHandler, loop: asyncio.AbstractEventLoop
) -> bool:
    """Run the handler; False means it could not run and the message must be redelivered."""
    try:
        event: Any = json.loads(message.data)
    except ValueError as exc:
        _LOGGER.warning("pubsub message ignored: %s", type(exc).__name__)
        return True
    if not isinstance(event, dict):
        _LOGGER.warning("pubsub message ignored: not an object")
        return True

    async def run_handler() -> None:
        await handler(event)

    coroutine = run_handler()
    try:
        future = asyncio.run_coroutine_threadsafe(coroutine, loop)
    except RuntimeError as exc:  # the loop is closed
        coroutine.close()
        _LOGGER.error("pubsub handler not run: %s", type(exc).__name__)
        return False
    try:
        future.result()
    except (CancelledError, asyncio.CancelledError) as exc:
        _LOGGER.error("pubsub handler not run: %s", type(exc).__name__)
        return False
    except Exception as exc:
        _LOGGER.error("pubsub handler failed: %s", type(exc).__name__)
    return True


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
