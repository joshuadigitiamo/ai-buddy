"""D-14 / MCP-07: per-identity token bucket (boundary: burst N passes, request N+1 is refused)."""

from collections.abc import AsyncIterator, Callable
from typing import Any

import httpx2
import pytest
from fastmcp import FastMCP
from tests.unit.mcp_server.conftest import BOT_EMAIL

from buddy_mcp.config import McpSettings
from buddy_mcp.gaplog import InMemoryGapLog
from buddy_mcp.server import build_app, build_server
from buddy_mcp.snapshot import IndexSnapshot

pytestmark = pytest.mark.anyio

_HEADERS = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}
_SECOND_BOT = "second-bot@demo-ai-buddy.iam.gserviceaccount.com"
_BURST = 3


async def _list_tools(http: httpx2.AsyncClient, token: str | None) -> dict[str, Any]:
    headers = dict(_HEADERS)
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    body = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
    response = await http.post("/mcp", json=body, headers=headers)
    assert response.status_code == 200
    payload: dict[str, Any] = response.json()
    return payload


def _limited(auth_settings: McpSettings) -> McpSettings:
    return auth_settings.model_copy(
        update={
            "rate_limit_rps": 0.001,
            "rate_limit_burst": _BURST,
            "bot_sa_emails": frozenset({BOT_EMAIL, _SECOND_BOT}),
        }
    )


@pytest.fixture
async def limited_client(
    make_auth_server: Callable[..., FastMCP], auth_settings: McpSettings
) -> AsyncIterator[httpx2.AsyncClient]:
    app = build_app(make_auth_server(settings=_limited(auth_settings)))
    async with app.router.lifespan_context(app):
        transport = httpx2.ASGITransport(app=app)
        async with httpx2.AsyncClient(transport=transport, base_url="http://localhost") as http:
            yield http


async def test_burst_passes_then_the_next_request_is_refused(
    limited_client: httpx2.AsyncClient, sign_bot_token: Callable[..., str]
) -> None:
    token = sign_bot_token()
    for _ in range(_BURST):
        assert "error" not in await _list_tools(limited_client, token)
    refused = await _list_tools(limited_client, token)
    assert "Rate limit exceeded" in refused["error"]["message"]


async def test_another_identity_is_still_served(
    limited_client: httpx2.AsyncClient, sign_bot_token: Callable[..., str]
) -> None:
    first = sign_bot_token()
    for _ in range(_BURST + 1):
        await _list_tools(limited_client, first)
    second = await _list_tools(limited_client, sign_bot_token(email=_SECOND_BOT))
    assert "error" not in second
    assert second["result"]["tools"]


async def test_anonymous_callers_share_one_bucket_when_auth_is_off(
    settings: McpSettings, snapshot: IndexSnapshot, gaplog: InMemoryGapLog
) -> None:
    config = settings.model_copy(update={"rate_limit_rps": 0.001, "rate_limit_burst": _BURST})
    app = build_app(build_server(config, snapshot=snapshot, gaplog=gaplog))
    async with app.router.lifespan_context(app):
        transport = httpx2.ASGITransport(app=app)
        async with httpx2.AsyncClient(transport=transport, base_url="http://localhost") as http:
            for _ in range(_BURST):
                assert "error" not in await _list_tools(http, None)
            refused = await _list_tools(http, None)
    assert "Rate limit exceeded" in refused["error"]["message"]
