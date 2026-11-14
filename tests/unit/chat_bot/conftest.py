"""Synthetic fixtures only: no handbook text, no names, no credentials."""

import copy
import json
from collections.abc import AsyncIterator, Callable, Iterator, Mapping, Sequence
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from fastmcp import FastMCP
from pydantic import BaseModel
from tests.unit.mcp_server.conftest import NOW, WEB_BASE, make_content, make_page, write_index

from buddy_bot.mcp_client import FastMcpConnector
from buddy_bot.ports import LlmOutputError, M, McpTools, ThreadMemory, Turn
from buddy_bot.schemas import AnswerDraft, Reformulation
from buddy_bot.service import BotService
from buddy_bot.workflow import WorkflowConfig, WorkflowDeps
from buddy_mcp.config import McpSettings
from buddy_mcp.gaplog import InMemoryGapLog
from buddy_mcp.models import GapReportOutput, GuidesSearchOutput, HandbookSearchOutput
from buddy_mcp.server import build_server
from buddy_mcp.snapshot import load_snapshot

ALLOWED = frozenset({"users/111111111111111111111"})
EVENTS_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "chat_events"

REFORMULATION = Reformulation(
    standalone_question="Come richiedo le ferie?",
    keywords_it=["ferie"],
    keywords_en=["chunking"],
    intent="question",
    sensitive_topic=None,
)
GOOD_DRAFT = AnswerDraft(
    answer="Invia la richiesta al responsabile con due settimane di anticipo.",
    citations=["handbook://02-ferie"],
    grounded=True,
    confidence=0.9,
)

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


class DictThreadMemory:
    """Thread memory in a dict; records calls and can be told to fail."""

    def __init__(self) -> None:
        self.turns: dict[str, list[Turn]] = {}
        self.recent_calls: list[tuple[str, int]] = []
        self.append_calls: list[tuple[str, Turn]] = []
        self.fail_recent = False
        self.fail_append = False

    @property
    def calls(self) -> int:
        return len(self.recent_calls) + len(self.append_calls)

    async def recent(self, key_source: str, n: int) -> list[Turn]:
        self.recent_calls.append((key_source, n))
        if self.fail_recent:
            raise RuntimeError("memory read failed")
        return self.turns.get(key_source, [])[-n:]

    async def append(self, key_source: str, turn: Turn) -> None:
        self.append_calls.append((key_source, turn))
        if self.fail_append:
            raise RuntimeError("memory write failed")
        self.turns.setdefault(key_source, []).append(turn)


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


def with_message(
    base: Mapping[str, Any], *, name: str | None = None, text: str | None = None
) -> dict[str, Any]:
    """A copy of a message event (either shape) with another message name and/or text."""
    event: dict[str, Any] = copy.deepcopy(dict(base))
    message = event["chat"]["messagePayload"]["message"] if "chat" in event else event["message"]
    if name is not None:
        message["name"] = name
    if text is not None:
        message["text"] = text
        message["argumentText"] = text
    return event


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
    settings = McpSettings(
        artifact_dir=directory, guides_web_base=WEB_BASE, auth_mode="off", deploy_env="local"
    )
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


ServiceFactory = Callable[..., BotService]


@pytest.fixture
def make_service(connector: RecordingConnector, workflow_config: WorkflowConfig) -> ServiceFactory:
    """Build a BotService over the real MCP server; keyword overrides replace any argument."""

    def build(
        llm: FakeLlm,
        *,
        chat: FakeChatApi | None = None,
        memory: ThreadMemory | None = None,
        **overrides: Any,
    ) -> BotService:
        arguments: dict[str, Any] = {
            "allowed_users": ALLOWED,
            "chat": chat if chat is not None else FakeChatApi(),
            "deps": WorkflowDeps(llm=llm, mcp=connector, config=workflow_config),
            "memory": memory if memory is not None else DictThreadMemory(),
            "memory_turns": 3,
            "video_thumbnail_url": "https://example.invalid/thumb.png",
        }
        arguments.update(overrides)
        return BotService(**arguments)

    return build
