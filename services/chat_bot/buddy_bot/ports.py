"""Ports of the chat bot (Ports & Adapters): every external system sits behind a Protocol.

The workflow and the service depend only on these shapes; adapters and test fakes implement them.
"""

from collections.abc import Awaitable, Callable, Mapping, Sequence
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from typing import Any, Protocol, TypeVar

from pydantic import BaseModel

from buddy_mcp.models import GapReportOutput, GuidesSearchOutput, HandbookSearchOutput

M = TypeVar("M", bound=BaseModel)

EventHandler = Callable[[Mapping[str, Any]], Awaitable[None]]


@dataclass(frozen=True, slots=True)
class Turn:
    """One question and the answer the bot gave (reformulation history only, D-12)."""

    question: str
    answer: str


class LlmError(Exception):
    """Base of every error an LlmClient raises."""


class LlmOutputError(LlmError):
    """The model output is still invalid after the one repair retry."""


class LlmUnavailableError(LlmError):
    """Transport error or timeout while calling the model."""


class LlmClient(Protocol):
    """Structured output from a model. Implementations raise only LlmError subclasses."""

    async def structured(
        self, schema: type[M], *, model: str, system: str, user: str, max_tokens: int
    ) -> M: ...


class McpTools(Protocol):
    """The Phase 2 tools the bot calls; results are the buddy_mcp.models envelopes (D-06)."""

    async def handbook_search(self, query: str) -> HandbookSearchOutput: ...

    async def guides_search(self, query: str) -> GuidesSearchOutput: ...

    async def report_gap(self, question: str, tried: Sequence[str]) -> GapReportOutput: ...


class McpConnector(Protocol):
    """Opens one MCP session per run (the server rate limit counts every request)."""

    def session(self) -> AbstractAsyncContextManager[McpTools]: ...


class ChatApi(Protocol):
    """Google Chat messages the bot creates and patches."""

    async def create_message(self, *, space: str, thread: str | None, text: str) -> str:
        """Create a message and return its resource name."""
        ...

    async def update_message(
        self, *, name: str, text: str, cards_v2: Sequence[Mapping[str, Any]]
    ) -> None: ...


class ThreadMemory(Protocol):
    """Recent turns per conversation; the key source is hashed by the adapter (D-11)."""

    async def recent(self, key_source: str, n: int) -> list[Turn]: ...

    async def append(self, key_source: str, turn: Turn) -> None: ...


class IntakePort(Protocol):
    """Event transport (Pub/Sub or HTTP): feeds decoded events to the handler."""

    async def run(self, handler: EventHandler) -> None: ...
