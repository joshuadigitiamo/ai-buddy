"""BotService.handle: allowlist, placeholder, workflow run, in-place patch (D-09).

`handle` never raises. Log lines carry fixed text and exception type names only, never event
fields or question text (BOT-11).
"""

import logging
import time
from collections.abc import Callable, Mapping
from typing import Any, Final

from buddy_bot.events import ChatEvent, normalize_event
from buddy_bot.ports import ChatApi, ThreadMemory, Turn
from buddy_bot.render import render_reply
from buddy_bot.schemas import BotReply
from buddy_bot.workflow import WorkflowDeps, run_workflow

PLACEHOLDER_TEXT: Final = "Sto cercando nelle fonti…"
INTRO_TEXT: Final = ""
USAGE_TEXT: Final = ""

_LOGGER = logging.getLogger("buddy_bot")

_REMEMBERED_KINDS: Final = frozenset({"answer", "refusal", "referral", "smalltalk"})


def memory_key_source(event: ChatEvent) -> str | None:
    """Conversation identity for thread memory (D-11 as amended by 03-01 memory_key b).

    A DM is one conversation per space; a room conversation is one thread. The adapter hashes
    the returned value, so no raw id is stored.
    """
    return event.space_name if event.is_dm else event.thread_name


class BotService:
    def __init__(
        self,
        *,
        allowed_users: frozenset[str],
        chat: ChatApi,
        deps: WorkflowDeps,
        memory: ThreadMemory,
        memory_turns: int,
        video_thumbnail_url: str | None,
        help_command_id: str | None = None,
        run_deadline_seconds: float = 120.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._allowed = frozenset(user.lower() for user in allowed_users)
        self._chat = chat
        self._deps = deps
        self._memory = memory
        self._memory_turns = memory_turns
        self._video_thumbnail_url = video_thumbnail_url
        self._help_command_id = help_command_id
        self._run_deadline_seconds = run_deadline_seconds
        self._clock = clock

    async def handle(self, payload: Mapping[str, Any]) -> None:
        """Answer one Chat event; any failure is logged by type and never propagates."""
        try:
            await self._handle(payload)
        except Exception as exc:
            _LOGGER.error("event handling failed: %s", type(exc).__name__)

    def _is_allowed(self, user_name: str | None, user_email: str | None) -> bool:
        return any(
            identity.lower() in self._allowed for identity in (user_name, user_email) if identity
        )

    async def _handle(self, payload: Mapping[str, Any]) -> None:
        event = normalize_event(payload)
        if event is None:
            return
        if not self._is_allowed(event.user_name, event.user_email):
            _LOGGER.info("event dropped: sender not allowed")
            return
        if event.kind != "message":
            return
        name = await self._chat.create_message(
            space=event.space_name, thread=event.thread_name, text=PLACEHOLDER_TEXT
        )
        key = memory_key_source(event)
        history = await self._recent(key)
        try:
            reply = await run_workflow(event.text, history, self._deps)
            rendered = render_reply(reply, video_thumbnail_url=self._video_thumbnail_url)
        except Exception as exc:
            _LOGGER.error("workflow failed: %s", type(exc).__name__)
            reply = BotReply(kind="error")
            rendered = render_reply(reply, video_thumbnail_url=None)
        await self._chat.update_message(name=name, text=rendered.text, cards_v2=rendered.cards_v2)
        if key is not None and reply.kind in _REMEMBERED_KINDS:
            await self._remember(
                key, Turn(question=event.text, answer=reply.answer or rendered.text)
            )

    async def _recent(self, key: str | None) -> list[Turn]:
        """History for the reformulation step only; a failing store means no history."""
        if key is None:
            return []
        try:
            return await self._memory.recent(key, self._memory_turns)
        except Exception as exc:
            _LOGGER.error("memory read failed: %s", type(exc).__name__)
            return []

    async def _remember(self, key: str, turn: Turn) -> None:
        try:
            await self._memory.append(key, turn)
        except Exception as exc:
            _LOGGER.error("memory write failed: %s", type(exc).__name__)
