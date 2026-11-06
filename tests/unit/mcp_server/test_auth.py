"""MCP-07 authentication: 401 with resource metadata, the bot's ID token, the user path."""

from collections.abc import AsyncIterator, Callable
from typing import Any

import httpx2
import pytest
from fastmcp import FastMCP
from fastmcp.server.auth import AccessToken, MultiAuth, OAuthProxy
from fastmcp.server.auth.providers.google import GoogleTokenVerifier
from key_value.aio.stores.memory import MemoryStore

from buddy_mcp.auth import DomainRestrictedGoogleVerifier, build_auth
from buddy_mcp.config import McpSettings
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


# --- human path: domain restriction -----------------------------------------------------------


def _google_token(claims: dict[str, Any]) -> AccessToken:
    return AccessToken(token="opaque", client_id="u-1", scopes=[], claims=claims)


def _patch_parent(monkeypatch: pytest.MonkeyPatch, result: AccessToken | None) -> None:
    async def fake(self: GoogleTokenVerifier, token: str) -> AccessToken | None:
        return result

    monkeypatch.setattr(GoogleTokenVerifier, "verify_token", fake)


def _domain_verifier() -> DomainRestrictedGoogleVerifier:
    return DomainRestrictedGoogleVerifier(allowed_domain="digitiamo.com")


@pytest.mark.parametrize("email", ["a@digitiamo.com", "A@DIGITIAMO.COM", "x.y+z@Digitiamo.Com"])
async def test_allowed_domain_is_accepted(monkeypatch: pytest.MonkeyPatch, email: str) -> None:
    _patch_parent(monkeypatch, _google_token({"email": email, "email_verified": True}))
    assert await _domain_verifier().verify_token("t") is not None


@pytest.mark.parametrize(
    "email",
    [
        "x@gmail.com",
        "a@sub.digitiamo.com",
        "a@digitiamo.com.evil.example",
        "a@evil.example@digitiamo.com.evil.example",
        "@digitiamo.com",
        "digitiamo.com",
        "",
        None,
    ],
)
async def test_other_domains_are_rejected(monkeypatch: pytest.MonkeyPatch, email: Any) -> None:
    _patch_parent(monkeypatch, _google_token({"email": email, "email_verified": True}))
    assert await _domain_verifier().verify_token("t") is None


@pytest.mark.parametrize("verified", [False, None, "false", "", 0])
async def test_unverified_email_is_rejected(monkeypatch: pytest.MonkeyPatch, verified: Any) -> None:
    claims = {"email": "a@digitiamo.com", "email_verified": verified}
    _patch_parent(monkeypatch, _google_token(claims))
    assert await _domain_verifier().verify_token("t") is None


async def test_missing_email_verified_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_parent(monkeypatch, _google_token({"email": "a@digitiamo.com"}))
    assert await _domain_verifier().verify_token("t") is None


async def test_tokeninfo_string_true_counts_as_verified(monkeypatch: pytest.MonkeyPatch) -> None:
    claims = {"email": "a@digitiamo.com", "email_verified": "true"}
    _patch_parent(monkeypatch, _google_token(claims))
    assert await _domain_verifier().verify_token("t") is not None


@pytest.mark.parametrize(
    "claims",
    [
        {"hd": "other.example"},
        {"google_user_data": {"hd": "other.example"}},
        {"hd": "digitiamo.com", "google_user_data": {"hd": "other.example"}},
    ],
)
async def test_hosted_domain_mismatch_is_rejected(
    monkeypatch: pytest.MonkeyPatch, claims: dict[str, Any]
) -> None:
    base = {"email": "a@digitiamo.com", "email_verified": True}
    _patch_parent(monkeypatch, _google_token({**base, **claims}))
    assert await _domain_verifier().verify_token("t") is None


async def test_matching_hosted_domain_is_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    claims = {
        "email": "a@digitiamo.com",
        "email_verified": True,
        "hd": "digitiamo.com",
        "google_user_data": {"hd": "DIGITIAMO.com"},
    }
    _patch_parent(monkeypatch, _google_token(claims))
    assert await _domain_verifier().verify_token("t") is not None


async def test_parent_rejection_is_final(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_parent(monkeypatch, None)
    assert await _domain_verifier().verify_token("t") is None


# --- human path: OAuth facade ---------------------------------------------------------------


async def test_protected_resource_metadata(client: httpx2.AsyncClient) -> None:
    response = await client.get("/.well-known/oauth-protected-resource/mcp")
    assert response.status_code == 200
    body = response.json()
    assert body["resource"] == "http://localhost/mcp"
    assert body["authorization_servers"]


async def test_authorization_server_metadata(client: httpx2.AsyncClient) -> None:
    response = await client.get("/.well-known/oauth-authorization-server")
    assert response.status_code == 200
    body = response.json()
    assert body["registration_endpoint"]
    assert "S256" in body["code_challenge_methods_supported"]
    assert body["client_id_metadata_document_supported"] is True


def _registration(redirect_uri: str) -> dict[str, Any]:
    return {
        "client_name": "pytest",
        "redirect_uris": [redirect_uri],
        "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"],
        "token_endpoint_auth_method": "none",
    }


async def test_registration_with_a_foreign_redirect_uri_is_rejected(
    client: httpx2.AsyncClient,
) -> None:
    response = await client.post("/register", json=_registration("https://evil.example/cb"))
    assert 400 <= response.status_code < 500


@pytest.mark.parametrize(
    "redirect_uri",
    [
        "https://claude.ai/api/mcp/auth_callback",
        "http://localhost:6274/callback",
        "http://127.0.0.1:33418/callback",
    ],
)
async def test_registration_with_an_allowed_redirect_uri_succeeds(
    client: httpx2.AsyncClient, redirect_uri: str
) -> None:
    response = await client.post("/register", json=_registration(redirect_uri))
    assert response.status_code == 201
    assert response.json()["client_id"]


class _SpyStore(MemoryStore):
    """Counts writes so a test can see that the proxy persists into the store it was given."""

    def __init__(self) -> None:
        super().__init__()
        self.writes = 0

    async def put(
        self,
        key: str,
        value: Any,
        *,
        collection: str | None = None,
        ttl: Any = None,
    ) -> None:
        self.writes += 1
        await super().put(key, value, collection=collection, ttl=ttl)


async def test_the_proxy_uses_the_store_it_was_given(
    make_auth_server: Callable[..., FastMCP],
) -> None:
    spy = _SpyStore()
    app = build_app(make_auth_server(storage=spy))
    async with app.router.lifespan_context(app):
        transport = httpx2.ASGITransport(app=app)
        async with httpx2.AsyncClient(transport=transport, base_url="http://localhost") as http:
            response = await http.post(
                "/register", json=_registration("https://claude.ai/api/mcp/auth_callback")
            )
    assert response.status_code == 201
    assert spy.writes >= 1


def test_build_auth_without_bot_accounts_is_the_proxy_alone(auth_settings: McpSettings) -> None:
    alone = auth_settings.model_copy(update={"bot_sa_emails": frozenset()})
    provider = build_auth(alone, storage=MemoryStore())
    assert isinstance(provider, OAuthProxy)
    assert isinstance(build_auth(auth_settings, storage=MemoryStore()), MultiAuth)
