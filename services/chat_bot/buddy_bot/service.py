"""BotService.handle: allowlist, placeholder, workflow run, in-place patch (D-09).

`handle` never raises. Log lines carry fixed text and exception type names only, never event
fields or question text (BOT-11).
"""

import logging
from collections.abc import Mapping
from typing import Any, Final

from buddy_bot.events import normalize_event
from buddy_bot.ports import ChatApi
from buddy_bot.render import render_reply
from buddy_bot.schemas import BotReply
from buddy_bot.workflow import WorkflowDeps, run_workflow

PLACEHOLDER_TEXT: Final = "Sto cercando nelle fonti…"

_LOGGER = logging.getLogger("buddy_bot")


class BotService:
    def __init__(
        self,
        *,
        allowed_users: frozenset[str],
        chat: ChatApi,
        deps: WorkflowDeps,
        video_thumbnail_url: str | None,
    ) -> None:
        self._allowed = frozenset(user.lower() for user in allowed_users)
        self._chat = chat
        self._deps = deps
        self._video_thumbnail_url = video_thumbnail_url

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
        try:
            reply = await run_workflow(event.text, [], self._deps)
            rendered = render_reply(reply, video_thumbnail_url=self._video_thumbnail_url)
        except Exception as exc:
            _LOGGER.error("workflow failed: %s", type(exc).__name__)
            rendered = render_reply(BotReply(kind="error"), video_thumbnail_url=None)
        await self._chat.update_message(name=name, text=rendered.text, cards_v2=rendered.cards_v2)
