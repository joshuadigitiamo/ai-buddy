"""BotService.handle: allowlist, dedupe, canned replies, placeholder, run, in-place patch (D-09).

`handle` never raises. Log lines carry fixed text and exception type names only, never event
fields or question text (BOT-11).
"""

import asyncio
import logging
import time
from collections.abc import Callable, Mapping, Sequence
from typing import Any, Final

from buddy_bot.events import ChatEvent, normalize_event
from buddy_bot.ports import ChatApi, ThreadMemory, Turn
from buddy_bot.render import ERROR_TEXT, RenderedMessage, render_reply
from buddy_bot.schemas import BotReply
from buddy_bot.workflow import WorkflowDeps, run_workflow

PLACEHOLDER_TEXT: Final = "Sto cercando nelle fonti…"
INTRO_TEXT: Final = (
    "Ciao, sono AI Buddy. Rispondo alle tue domande usando il manuale aziendale e le Guide "
    "tecniche, e indico sempre la fonte. Scrivimi una domanda, oppure digita /aiuto per vedere "
    "come funziono."
)
USAGE_TEXT: Final = (
    "Scrivimi una domanda in linguaggio naturale. Due esempi:\n\n"
    "• Come richiedo le ferie? (manuale aziendale)\n\n"
    "• Come funziona il chunking nei sistemi RAG? (Guide tecniche)\n\n"
    "Rispondo solo da fonti ufficiali e cito sempre la fonte. "
    "Se non trovo la risposta te lo dico e ti indico a chi chiedere."
)
HELP_PREFIX: Final = "/aiuto"
DEDUPE_TTL_SECONDS: Final = 600
DEDUPE_MAX_ENTRIES: Final = 1024

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
        entries = (user.strip().lower() for user in allowed_users)
        self._allowed = frozenset(entry for entry in entries if entry)
        self._chat = chat
        self._deps = deps
        self._memory = memory
        self._memory_turns = memory_turns
        self._video_thumbnail_url = video_thumbnail_url
        self._help_command_id = help_command_id
        self._run_deadline_seconds = run_deadline_seconds
        self._clock = clock
        self._seen: dict[str, float] = {}

    async def handle(self, payload: Mapping[str, Any]) -> None:
        """Answer one Chat event; any failure is logged by type and never propagates."""
        try:
            await self._handle(payload)
        except Exception as exc:
            _LOGGER.error("event handling failed: %s", type(exc).__name__)

    def _is_allowed(self, user_name: str | None, user_email: str | None) -> bool:
        return any(
            identity.strip().lower() in self._allowed
            for identity in (user_name, user_email)
            if identity
        )

    def _is_duplicate(self, message_name: str | None) -> bool:
        """Idempotency key: a message name seen within the TTL is a redelivery."""
        if message_name is None:
            return False
        now = self._clock()
        while self._seen and now - next(iter(self._seen.values())) >= DEDUPE_TTL_SECONDS:
            del self._seen[next(iter(self._seen))]
        if message_name in self._seen:
            return True
        self._seen[message_name] = now
        while len(self._seen) > DEDUPE_MAX_ENTRIES:
            del self._seen[next(iter(self._seen))]
        return False

    def _is_help(self, event: ChatEvent) -> bool:
        by_id = event.command_id is not None and event.command_id == self._help_command_id
        return by_id or event.text.lower().startswith(HELP_PREFIX)

    async def _handle(self, payload: Mapping[str, Any]) -> None:
        event = normalize_event(payload)
        if event is None or event.is_bot_sender:
            return
        if not self._is_allowed(event.user_name, event.user_email):
            _LOGGER.info("event dropped: sender not allowed")
            return
        if event.kind == "removed":
            return
        if event.kind != "added" and self._is_duplicate(event.message_name):
            return
        if event.kind == "added":
            await self._say(event, INTRO_TEXT)
        elif event.kind == "command" or self._is_help(event) or not event.text:
            await self._say(event, USAGE_TEXT)
        else:
            await self._answer(event)

    async def _say(self, event: ChatEvent, text: str) -> None:
        """A fixed reply: one message, no placeholder, no model or MCP call (D-13)."""
        await self._chat.create_message(space=event.space_name, thread=event.thread_name, text=text)

    async def _run(self, event: ChatEvent, key: str | None) -> tuple[BotReply, RenderedMessage]:
        """History, workflow and rendering under the run deadline; any failure is an error reply."""
        try:
            async with asyncio.timeout(self._run_deadline_seconds):
                history = await self._recent(key)
                reply = await run_workflow(event.text, history, self._deps)
                rendered = render_reply(reply, video_thumbnail_url=self._video_thumbnail_url)
        except Exception as exc:
            _LOGGER.error("run failed: %s", type(exc).__name__)
            reply = BotReply(kind="error")
            rendered = render_reply(reply, video_thumbnail_url=None)
        return reply, rendered

    async def _answer(self, event: ChatEvent) -> None:
        name = await self._chat.create_message(
            space=event.space_name, thread=event.thread_name, text=PLACEHOLDER_TEXT
        )
        key = memory_key_source(event)
        reply, rendered = await self._run(event, key)
        if not await self._deliver(event, name, rendered):
            return
        if key is not None and reply.kind in _REMEMBERED_KINDS:
            await self._remember(
                key, Turn(question=event.text, answer=reply.answer or rendered.text)
            )

    async def _deliver(self, event: ChatEvent, name: str, rendered: RenderedMessage) -> bool:
        """Patch the placeholder; on failure retry without the card, then post the error text.

        Returns True when the answer reached the user. The last resort is a new message, so the
        placeholder is never the final reply; its own failure is logged and not raised.
        """
        attempts: tuple[Sequence[Mapping[str, Any]], ...] = (rendered.cards_v2, [])
        for cards in attempts:
            try:
                await self._chat.update_message(name=name, text=rendered.text, cards_v2=cards)
                return True
            except Exception as exc:
                _LOGGER.error("reply patch failed: %s", type(exc).__name__)
        try:
            await self._chat.create_message(
                space=event.space_name, thread=event.thread_name, text=ERROR_TEXT
            )
        except Exception as exc:
            _LOGGER.error("error reply failed: %s", type(exc).__name__)
        return False

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
