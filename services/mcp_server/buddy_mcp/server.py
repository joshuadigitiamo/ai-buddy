"""FastMCP composition and the stateless JSON ASGI app (MCP-01)."""

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Final

from fastmcp import FastMCP
from starlette.applications import Starlette

from buddy_mcp.config import McpSettings
from buddy_mcp.gap_tool import register_gap_tool
from buddy_mcp.gaplog import GapLog
from buddy_mcp.guides_tools import register_guides_tools
from buddy_mcp.handbook_tools import register_handbook_tools
from buddy_mcp.snapshot import IndexSnapshot

SERVER_NAME: Final = "digitiamo-buddy"

_INSTRUCTIONS: Final = (
    "Cite the source_url and revision_date returned by the tools in every answer. "
    "When a tool returns status no_results, refuse to answer and call buddy_report_gap."
)


def _utc_now() -> datetime:
    return datetime.now(UTC)


def build_server(
    settings: McpSettings,
    *,
    snapshot: IndexSnapshot,
    gaplog: GapLog,
    now: Callable[[], datetime] = _utc_now,
) -> FastMCP:
    """Compose the FastMCP server with every tool group registered."""
    mcp = FastMCP(SERVER_NAME, instructions=_INSTRUCTIONS)
    register_guides_tools(mcp, snapshot, settings)
    register_handbook_tools(mcp, snapshot)
    register_gap_tool(
        mcp,
        gaplog=gaplog,
        build_id=snapshot.meta.build_id,
        ttl_days=settings.gap_ttl_days,
        now=now,
    )
    return mcp


def build_app(mcp: FastMCP) -> Starlette:
    """Stateless streamable HTTP app answering with plain JSON, no held-open stream."""
    return mcp.http_app(stateless_http=True, json_response=True)
