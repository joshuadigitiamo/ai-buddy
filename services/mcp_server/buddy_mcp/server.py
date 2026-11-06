"""FastMCP composition and the stateless JSON ASGI app (MCP-01)."""

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, Final
from urllib.parse import urlsplit

from fastmcp import FastMCP
from fastmcp.server.auth import AuthProvider
from fastmcp.server.middleware.rate_limiting import RateLimitingMiddleware
from starlette.applications import Starlette

from buddy_mcp.auth import caller_identity
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
    auth: AuthProvider | None = None,
    now: Callable[[], datetime] = _utc_now,
) -> FastMCP:
    """Compose the FastMCP server with every tool group registered."""
    mcp = FastMCP(SERVER_NAME, instructions=_INSTRUCTIONS, auth=auth)
    # D-14: in memory, per caller, per instance. Every request (initialize, tools/list) takes a
    # token, hence the generous burst default.
    mcp.add_middleware(
        RateLimitingMiddleware(
            max_requests_per_second=settings.rate_limit_rps,
            burst_capacity=settings.rate_limit_burst,
            get_client_id=caller_identity,
        )
    )
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


_LOOPBACK_HOSTS: Final = ("localhost", "127.0.0.1")
_CLAUDE_ORIGIN: Final = "https://claude.ai"


def host_kwargs(settings: McpSettings | None) -> dict[str, Any]:
    """Keyword arguments for fastmcp's Host/Origin guard (ASVS V13, DNS-rebinding defence).

    Allowed hosts: the host of MCP_PUBLIC_BASE_URL when set, plus localhost and 127.0.0.1 (any
    port). Allowed origins: the public origin, claude.ai and loopback origins. The same dict feeds
    the ASGI app and the process runner, so both enforce the same rule.
    """
    hosts = list(_LOOPBACK_HOSTS)
    origins = [_CLAUDE_ORIGIN, *(f"http://{host}:*" for host in _LOOPBACK_HOSTS)]
    if settings is not None and settings.mcp_public_base_url:
        public = urlsplit(settings.mcp_public_base_url)
        if public.hostname and public.hostname not in hosts:
            hosts.append(public.hostname)
        origins.append(f"{public.scheme}://{public.netloc}")
    return {
        "host_origin_protection": True,
        "allowed_hosts": hosts,
        "allowed_origins": origins,
    }


def build_app(mcp: FastMCP, settings: McpSettings | None = None) -> Starlette:
    """Stateless streamable HTTP app answering with plain JSON, no held-open stream."""
    return mcp.http_app(stateless_http=True, json_response=True, **host_kwargs(settings))
