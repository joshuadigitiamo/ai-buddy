"""Synthetic fixtures only: no handbook text, no names, no credentials."""

import json
from collections.abc import AsyncIterator, Iterator, Mapping, Sequence
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from fastmcp import FastMCP
from pydantic import BaseModel
from tests.unit.mcp_server.conftest import NOW, WEB_BASE, make_content, make_page, write_index

from buddy_bot.mcp_client import FastMcpConnector
from buddy_bot.ports import LlmOutputError, M, McpTools
from buddy_bot.workflow import WorkflowConfig
from buddy_mcp.config import McpSettings
from buddy_mcp.gaplog import InMemoryGapLog
from buddy_mcp.models import GapReportOutput, GuidesSearchOutput, HandbookSearchOutput
from buddy_mcp.server import build_server
from buddy_mcp.snapshot import load_snapshot

ALLOWED = frozenset({"users/111111111111111111111"})
EVENTS_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "chat_events"

CONTACTS_PAGE = make_page(
    "05-contatti",
    4,
    "Contatti",
    "Per domande su contratto, ferie e malattia scrivi a HR: hr@example.invalid.",
    "2026-10-10T00:00:00+00:00",
)


@dataclass(frozen=True, slots=True)
class LlmCall:
    schema: type[BaseModel]
    model: str
    system: str
    user: str


class FakeLlm:
    """Returns the next scripted item per schema; an exception item is raised.

    With no scripted item left for a schema it raises LlmOutputError, so later plans can add LLM
    steps without breaking tests written before them.
    """

    def __init__(self, script: Mapping[type, Sequence[BaseModel | Exception]]) -> None:
        self._script = {schema: list(items) for schema, items in script.items()}
        self.calls: list[LlmCall] = []

    async def structured(
        self, schema: type[M], *, model: str, system: str, user: str, max_tokens: int
    ) -> M:
        self.calls.append(LlmCall(schema, model, system, user))
        queue = self._script.get(schema)
        if not queue:
            raise LlmOutputError("no scripted item")
        item = queue.pop(0)
        if isinstance(item, Exception):
            raise item
        assert isinstance(item, schema)
        return item


@dataclass(frozen=True, slots=True)
class CreatedMessage:
    space: str
    thread: str | None
    text: str


@dataclass(frozen=True, slots=True)
class UpdatedMessage:
    name: str
    text: str
    cards_v2: tuple[Mapping[str, Any], ...]


class FakeChatApi:
    def __init__(self) -> None:
        self.created: list[CreatedMessage] = []
        self.updated: list[UpdatedMessage] = []

    async def create_message(self, *, space: str, thread: str | None, text: str) -> str:
        self.created.append(CreatedMessage(space, thread, text))
        return f"{space}/messages/placeholder-{len(self.created)}"

    async def update_message(
        self, *, name: str, text: str, cards_v2: Sequence[Mapping[str, Any]]
    ) -> None:
        self.updated.append(UpdatedMessage(name, text, tuple(cards_v2)))


class _RecordingTools:
    def __init__(self, inner: McpTools, owner: "RecordingConnector") -> None:
        self._inner = inner
        self._owner = owner

    async def handbook_search(self, query: str) -> HandbookSearchOutput:
        self._owner.calls.append("handbook_search")
        result = await self._inner.handbook_search(query)
        self._owner.returned_urls.extend(r.source_url for r in result.results)
        return result

    async def guides_search(self, query: str) -> GuidesSearchOutput:
        self._owner.calls.append("guides_search")
        result = await self._inner.guides_search(query)
        self._owner.returned_urls.extend(r.source_url for r in result.results)
        return result

    async def report_gap(self, question: str, tried: Sequence[str]) -> GapReportOutput:
        self._owner.calls.append("buddy_report_gap")
        return await self._inner.report_gap(question, tried)


class RecordingConnector:
    """Wraps a FastMcpConnector; records tool method names and the source_urls returned."""

    def __init__(self, inner: FastMcpConnector) -> None:
        self._inner = inner
        self.calls: list[str] = []
        self.returned_urls: list[str] = []

    def session(self) -> AbstractAsyncContextManager[McpTools]:
        return self._session()

    @asynccontextmanager
    async def _session(self) -> AsyncIterator[McpTools]:
        async with self._inner.session() as tools:
            yield _RecordingTools(tools, self)


def load_event(name: str) -> dict[str, Any]:
    """Load a recorded Chat event fixture by file stem."""
    loaded: dict[str, Any] = json.loads((EVENTS_DIR / f"{name}.json").read_text(encoding="utf-8"))
    return loaded


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def gaplog() -> InMemoryGapLog:
    return InMemoryGapLog()


@pytest.fixture
def mcp_server(tmp_path: Path, gaplog: InMemoryGapLog) -> Iterator[FastMCP]:
    base = make_content()
    content = make_content(pages=(*base.handbook, CONTACTS_PAGE))
    directory = tmp_path / "artifacts"
    write_index(directory, content)
    snapshot = load_snapshot(directory / "index.db")
    settings = McpSettings(artifact_dir=directory, guides_web_base=WEB_BASE, auth_mode="off")
    yield build_server(settings, snapshot=snapshot, gaplog=gaplog, now=lambda: NOW)
    snapshot.reader.close()
    snapshot.handbook_index.close()


@pytest.fixture
def connector(mcp_server: FastMCP) -> RecordingConnector:
    return RecordingConnector(FastMcpConnector(mcp_server))


@pytest.fixture
def workflow_config() -> WorkflowConfig:
    return WorkflowConfig(
        reformulate_model="test-haiku", answer_model="test-sonnet", confidence_threshold=0.7
    )
