"""fastmcp Client adapter: one session per run, results parsed per the D-06 contract.

The bot calls only handbook_search, guides_search and buddy_report_gap. It never lists tools,
never parses the prose rendering and never touches index.db.
"""

import asyncio
import threading
import time
from collections.abc import AsyncGenerator, AsyncIterator, Callable, Generator, Mapping, Sequence
from contextlib import asynccontextmanager
from typing import Any, TypeVar

import httpx2
from fastmcp import Client, FastMCP
from google.auth.transport.requests import Request
from google.oauth2 import id_token
from pydantic import BaseModel

from buddy_bot.schemas import Evidence
from buddy_mcp.models import GapReportOutput, GuidesSearchOutput, HandbookSearchOutput

T = TypeVar("T", bound=BaseModel)


class McpToolError(Exception):
    """A tool call failed or returned an unusable payload; the message names the tool only."""


class GoogleIdTokenAuth(httpx2.Auth):
    """Bearer auth for the MCP server: the bot's own Google ID token for ``audience``.

    The token comes from ``fetch_id_token`` (the service-account file in
    GOOGLE_APPLICATION_CREDENTIALS, else the metadata server on Cloud Run) and is cached in
    memory for ``lifetime_seconds`` (below the one-hour token life). It is never logged. The
    fetch blocks, so the async flow runs it in a worker thread; nothing is fetched until the
    first request.
    """

    def __init__(
        self,
        audience: str,
        *,
        fetch: Callable[[Request, str], str] = id_token.fetch_id_token,
        lifetime_seconds: float = 3000.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._audience = audience
        self._fetch_token = fetch
        self._lifetime_seconds = lifetime_seconds
        self._clock = clock
        self._lock = threading.Lock()
        self._token: str | None = None
        self._fetched_at = 0.0

    def _cached(self) -> str | None:
        if self._token is not None and self._clock() - self._fetched_at < self._lifetime_seconds:
            return self._token
        return None

    def _token_value(self) -> str:
        with self._lock:
            cached = self._cached()
            if cached is not None:
                return cached
            token = self._fetch_token(Request(), self._audience)
            self._token = token
            self._fetched_at = self._clock()
            return token

    def sync_auth_flow(
        self, request: httpx2.Request
    ) -> Generator[httpx2.Request, httpx2.Response, None]:
        request.headers["Authorization"] = f"Bearer {self._token_value()}"
        yield request

    async def async_auth_flow(
        self, request: httpx2.Request
    ) -> AsyncGenerator[httpx2.Request, httpx2.Response]:
        token = self._cached() or await asyncio.to_thread(self._token_value)
        request.headers["Authorization"] = f"Bearer {token}"
        yield request


def evidence_from(
    handbook: HandbookSearchOutput, guides: GuidesSearchOutput
) -> dict[str, Evidence]:
    """Map tool results to Evidence keyed by source_url."""
    found: dict[str, Evidence] = {}
    for page in handbook.results:
        found[page.source_url] = Evidence(
            source_url=page.source_url,
            kind="handbook",
            title=page.title,
            text=page.text,
            revision_date=page.revision_date,
            revision_kind=page.revision_kind,
        )
    for section in guides.results:
        found[section.source_url] = Evidence(
            source_url=section.source_url,
            kind="guides",
            title=section.heading,
            text=section.text,
            revision_date=section.revision_date,
            revision_kind=section.revision_kind,
            video_url=section.video_url,
        )
    return found


class FastMcpTools:
    """The three tools the bot uses, over one open fastmcp session."""

    def __init__(self, client: "Client[Any]", *, handbook_limit: int, guides_limit: int) -> None:
        self._client = client
        self._handbook_limit = handbook_limit
        self._guides_limit = guides_limit

    async def _call(self, tool: str, arguments: Mapping[str, Any], model: type[T]) -> T:
        try:
            result = await self._client.call_tool(tool, dict(arguments), raise_on_error=False)
        except Exception as exc:
            raise McpToolError(f"{tool} failed: {type(exc).__name__}") from None
        if result.is_error or result.structured_content is None:
            raise McpToolError(f"{tool} returned no structured result")
        try:
            return model.model_validate(result.structured_content)
        except ValueError:
            raise McpToolError(f"{tool} returned an invalid structured result") from None

    async def handbook_search(self, query: str) -> HandbookSearchOutput:
        return await self._call(
            "handbook_search",
            {"query": query, "limit": self._handbook_limit},
            HandbookSearchOutput,
        )

    async def guides_search(self, query: str) -> GuidesSearchOutput:
        return await self._call(
            "guides_search", {"query": query, "limit": self._guides_limit}, GuidesSearchOutput
        )

    async def report_gap(self, question: str, tried: Sequence[str]) -> GapReportOutput:
        return await self._call(
            "buddy_report_gap", {"question": question, "tried": list(tried)}, GapReportOutput
        )


class FastMcpConnector:
    """Opens one fastmcp Client per run; `target` is a URL or an in-process FastMCP server."""

    def __init__(
        self,
        target: str | FastMCP,
        *,
        auth: httpx2.Auth | None = None,
        handbook_limit: int = 3,
        guides_limit: int = 4,
    ) -> None:
        self._target = target
        self._auth = auth
        self._handbook_limit = handbook_limit
        self._guides_limit = guides_limit

    @asynccontextmanager
    async def session(self) -> AsyncIterator[FastMcpTools]:
        async with Client(self._target, auth=self._auth) as client:
            yield FastMcpTools(
                client, handbook_limit=self._handbook_limit, guides_limit=self._guides_limit
            )
