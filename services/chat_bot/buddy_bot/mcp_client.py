"""fastmcp Client adapter: one session per run, results parsed per the D-06 contract.

The bot calls only handbook_search, guides_search and buddy_report_gap. It never lists tools,
never parses the prose rendering and never touches index.db.
"""

from collections.abc import AsyncIterator, Mapping, Sequence
from contextlib import asynccontextmanager
from typing import Any, TypeVar

import httpx2
from fastmcp import Client, FastMCP
from pydantic import BaseModel

from buddy_bot.schemas import Evidence
from buddy_mcp.models import GapReportOutput, GuidesSearchOutput, HandbookSearchOutput

T = TypeVar("T", bound=BaseModel)


class McpToolError(Exception):
    """A tool call failed or returned an unusable payload; the message names the tool only."""


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
