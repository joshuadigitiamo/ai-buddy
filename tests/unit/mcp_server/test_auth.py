"""MCP-07 authentication: 401 with resource metadata, the bot's ID token, the user path."""

from collections.abc import AsyncIterator, Callable
from typing import Any

import httpx2
import pytest
from fastmcp import FastMCP

from buddy_mcp.server import build_app

pytestmark = pytest.mark.anyio

_HEADERS = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}
_TOOLS = {
    "guides_search",
    "guides_get_section",
    "handbook_search",
    "handbook_get",
    "buddy_report_gap",
}


def _rpc(method: str, params: dict[str, Any], request_id: int = 1) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}


def _bearer(token: str) -> dict[str, str]:
    return {**_HEADERS, "Authorization": f"Bearer {token}"}


@pytest.fixture
async def client(make_auth_server: Callable[..., FastMCP]) -> AsyncIterator[httpx2.AsyncClient]:
    app = build_app(make_auth_server())
    async with app.router.lifespan_context(app):
        transport = httpx2.ASGITransport(app=app)
        async with httpx2.AsyncClient(transport=transport, base_url="http://localhost") as http:
            yield http


async def test_no_token_is_401_with_resource_metadata(client: httpx2.AsyncClient) -> None:
    params = {
        "protocolVersion": "2025-11-25",
        "capabilities": {},
        "clientInfo": {"name": "pytest", "version": "0"},
    }
    response = await client.post("/mcp", json=_rpc("initialize", params), headers=_HEADERS)
    assert response.status_code == 401
    challenge = response.headers["www-authenticate"]
    expected = 'resource_metadata="http://localhost/.well-known/oauth-protected-resource/mcp"'
    assert expected in challenge


async def test_bot_token_lists_tools(
    client: httpx2.AsyncClient, sign_bot_token: Callable[..., str]
) -> None:
    response = await client.post(
        "/mcp", json=_rpc("tools/list", {}), headers=_bearer(sign_bot_token())
    )
    assert response.status_code == 200
    names = {tool["name"] for tool in response.json()["result"]["tools"]}
    assert names == _TOOLS


@pytest.mark.parametrize(
    "overrides",
    [
        pytest.param({"aud": "https://other.example"}, id="wrong-audience"),
        pytest.param({"email": "intruder@demo-ai-buddy.iam.gserviceaccount.com"}, id="not-listed"),
        pytest.param({"verified": False}, id="email-not-verified"),
        pytest.param({"expires_in": -60}, id="expired"),
        pytest.param({"issuer": "https://evil.example"}, id="wrong-issuer"),
        pytest.param({"extra_claims": {"exp": None}}, id="no-expiry"),
    ],
)
async def test_bot_token_rejections(
    client: httpx2.AsyncClient, sign_bot_token: Callable[..., str], overrides: dict[str, Any]
) -> None:
    token = sign_bot_token(**overrides)
    response = await client.post("/mcp", json=_rpc("tools/list", {}), headers=_bearer(token))
    assert response.status_code == 401


async def test_garbage_token_is_401(client: httpx2.AsyncClient) -> None:
    response = await client.post(
        "/mcp", json=_rpc("tools/list", {}), headers=_bearer("not.a.token")
    )
    assert response.status_code == 401
