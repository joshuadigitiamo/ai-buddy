"""FastMCP composition and the stateless JSON ASGI app (MCP-01)."""

from typing import Final

from fastmcp import FastMCP
from starlette.applications import Starlette

from buddy_mcp.config import McpSettings
from buddy_mcp.guides_tools import register_guides_tools
from buddy_mcp.snapshot import IndexSnapshot

SERVER_NAME: Final = "digitiamo-buddy"

_INSTRUCTIONS: Final = (
    "Cite the source_url and revision_date returned by the tools in every answer. "
    "When a tool returns status no_results, refuse to answer and call buddy_report_gap."
)


def build_server(settings: McpSettings, *, snapshot: IndexSnapshot) -> FastMCP:
    """Compose the FastMCP server with every tool group registered."""
    mcp = FastMCP(SERVER_NAME, instructions=_INSTRUCTIONS)
    register_guides_tools(mcp, snapshot, settings)
    return mcp


def build_app(mcp: FastMCP) -> Starlette:
    """Stateless streamable HTTP app answering with plain JSON, no held-open stream."""
    return mcp.http_app(stateless_http=True, json_response=True)
