"""MCP-01 transport: stateless JSON over the ASGI app, plus the tracer slice end to end."""

from collections.abc import AsyncIterator
from typing import Any

import httpx2
import pytest
from fastmcp import FastMCP
from tests.unit.mcp_server.conftest import SHA, WEB_BASE

from buddy_mcp.server import build_app

pytestmark = pytest.mark.anyio

_HEADERS = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}


@pytest.fixture
async def client(server: FastMCP) -> AsyncIterator[httpx2.AsyncClient]:
    app = build_app(server)
    async with app.router.lifespan_context(app):
        transport = httpx2.ASGITransport(app=app)
        async with httpx2.AsyncClient(transport=transport, base_url="http://localhost") as http:
            yield http


def _rpc(method: str, params: dict[str, Any], request_id: int = 1) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}


async def test_initialize_is_stateless_json(client: httpx2.AsyncClient) -> None:
    params = {
        "protocolVersion": "2025-11-25",
        "capabilities": {},
        "clientInfo": {"name": "pytest", "version": "0"},
    }
    response = await client.post("/mcp", json=_rpc("initialize", params), headers=_HEADERS)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert "mcp-session-id" not in response.headers


async def test_get_mcp_is_not_a_stream(client: httpx2.AsyncClient) -> None:
    response = await client.get("/mcp", headers=_HEADERS)
    assert response.status_code == 405


async def test_guides_search_over_http_is_cited(client: httpx2.AsyncClient) -> None:
    body = _rpc("tools/call", {"name": "guides_search", "arguments": {"query": "chunking"}})
    response = await client.post("/mcp", json=body, headers=_HEADERS)
    assert response.status_code == 200
    result = response.json()["result"]
    assert result["isError"] is False
    first = result["structuredContent"]["results"][0]
    expected_url = f"{WEB_BASE}/blob/{SHA}/AI-Engineering/DEMO_GUIDE.md#L10-L14"
    assert first["source_url"] == expected_url
    assert first["revision_date"] == "2026-11-03T10:00:00+00:00"
    assert first["revision_kind"] == "indexed_on"
    assert first["video_url"] == "https://videos.example.invalid/demo.mp4#t=12"
    assert expected_url in result["content"][0]["text"]
