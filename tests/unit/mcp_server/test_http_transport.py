"""MCP-01 transport: stateless JSON over the ASGI app, plus the tracer slice end to end."""

import os
from collections.abc import AsyncIterator, Callable
from pathlib import Path
from typing import Any

import fastmcp
import httpx2
import pytest
from fastmcp import FastMCP
from tests.unit.mcp_server.conftest import SHA, WEB_BASE

from buddy_mcp.config import McpSettings
from buddy_mcp.server import build_app, host_kwargs

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


# --- Host / Origin protection (ASVS V13, DNS rebinding) ------------------------------------------


@pytest.fixture
async def guarded(server: FastMCP, settings: McpSettings) -> AsyncIterator[httpx2.AsyncClient]:
    app = build_app(server, settings)
    async with app.router.lifespan_context(app):
        transport = httpx2.ASGITransport(app=app)
        async with httpx2.AsyncClient(transport=transport, base_url="http://localhost") as http:
            yield http


def _list_tools() -> dict[str, Any]:
    return _rpc("tools/list", {})


async def test_foreign_host_is_rejected_before_any_tool(guarded: httpx2.AsyncClient) -> None:
    body = _rpc("tools/call", {"name": "guides_search", "arguments": {"query": "chunking"}})
    response = await guarded.post("/mcp", json=body, headers={**_HEADERS, "Host": "evil.example"})
    assert 400 <= response.status_code < 500
    assert "result" not in response.text


async def test_foreign_origin_is_rejected(guarded: httpx2.AsyncClient) -> None:
    headers = {**_HEADERS, "Origin": "https://evil.example"}
    response = await guarded.post("/mcp", json=_list_tools(), headers=headers)
    assert 400 <= response.status_code < 500


@pytest.mark.parametrize("origin", ["https://claude.ai", "http://localhost:6274"])
async def test_allowed_origins_are_served(guarded: httpx2.AsyncClient, origin: str) -> None:
    headers = {**_HEADERS, "Origin": origin}
    response = await guarded.post("/mcp", json=_list_tools(), headers=headers)
    assert response.status_code == 200


async def test_localhost_without_origin_is_served(guarded: httpx2.AsyncClient) -> None:
    response = await guarded.post("/mcp", json=_list_tools(), headers=_HEADERS)
    assert response.status_code == 200


async def test_public_host_is_served_and_others_are_not(
    server: FastMCP, settings: McpSettings
) -> None:
    config = settings.model_copy(update={"mcp_public_base_url": "https://buddy.example"})
    app = build_app(server, config)
    async with app.router.lifespan_context(app):
        transport = httpx2.ASGITransport(app=app)
        async with httpx2.AsyncClient(transport=transport, base_url="https://buddy.example") as c:
            served = await c.post("/mcp", json=_list_tools(), headers=_HEADERS)
            other = await c.post(
                "/mcp", json=_list_tools(), headers={**_HEADERS, "Host": "evil.example"}
            )
    assert served.status_code == 200
    assert 400 <= other.status_code < 500


def test_host_kwargs_cover_the_public_host_and_loopback(settings: McpSettings) -> None:
    config = settings.model_copy(update={"mcp_public_base_url": "https://buddy.example"})
    kwargs = host_kwargs(config)
    assert {"buddy.example", "localhost", "127.0.0.1"} <= set(kwargs["allowed_hosts"])
    assert "https://buddy.example" in kwargs["allowed_origins"]
    assert "https://claude.ai" in kwargs["allowed_origins"]
    assert host_kwargs(None)["allowed_hosts"]


# --- MCP-01: nothing is written to disk -------------------------------------------------------


def _listing(root: Path) -> set[str]:
    if not root.exists():
        return set()
    return {str(path.relative_to(root)) for path in root.rglob("*")} | {"."}


async def test_serving_writes_nothing_to_disk(
    make_auth_server: Callable[..., FastMCP],
    sign_bot_token: Callable[..., str],
    auth_settings: McpSettings,
    index_dir: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = tmp_path / "home"
    work = tmp_path / "work"
    home.mkdir()
    work.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.chdir(work)
    fastmcp_home = Path(str(getattr(fastmcp.settings, "home", home / "absent-fastmcp-home")))
    watched = {"home": home, "cwd": work, "artifacts": index_dir, "fastmcp": fastmcp_home}
    before = {name: _listing(path) for name, path in watched.items()}

    app = build_app(make_auth_server(), auth_settings)
    token = sign_bot_token()
    async with app.router.lifespan_context(app):
        transport = httpx2.ASGITransport(app=app)
        async with httpx2.AsyncClient(transport=transport, base_url="http://localhost") as http:
            anonymous = await http.post("/mcp", json=_rpc("initialize", {}), headers=_HEADERS)
            call = _rpc("tools/call", {"name": "guides_search", "arguments": {"query": "chunking"}})
            served = await http.post(
                "/mcp", json=call, headers={**_HEADERS, "Authorization": f"Bearer {token}"}
            )
            resource = await http.get("/.well-known/oauth-protected-resource/mcp")
            server_meta = await http.get("/.well-known/oauth-authorization-server")
            registered = await http.post(
                "/register",
                json={
                    "client_name": "pytest",
                    "redirect_uris": ["https://claude.ai/api/mcp/auth_callback"],
                    "token_endpoint_auth_method": "none",
                },
            )

    assert anonymous.status_code == 401
    assert served.status_code == 200
    assert resource.status_code == 200
    assert server_meta.status_code == 200
    assert registered.status_code == 201
    assert {name: _listing(path) for name, path in watched.items()} == before
    assert os.getcwd() == str(work)
