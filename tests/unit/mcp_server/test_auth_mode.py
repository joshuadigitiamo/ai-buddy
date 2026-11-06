"""D-13: AUTH_MODE=off works for local and kind use, and is refused on Cloud Run (K_SERVICE)."""

import logging
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import httpx2
import pytest
from fastmcp import FastMCP
from key_value.aio.stores.memory import MemoryStore
from pydantic import ValidationError
from tests.unit.mcp_server.conftest import (
    BOT_EMAIL,
    FAKE_CLIENT_ID,
    FAKE_CLIENT_SECRET,
    FAKE_SIGNING_KEY,
    PUBLIC_BASE_URL,
    WEB_BASE,
)

from buddy_mcp.auth import build_auth
from buddy_mcp.config import McpSettings
from buddy_mcp.server import build_app

pytestmark = pytest.mark.anyio

_HEADERS = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}


@pytest.fixture(autouse=True)
def _outside_cloud_run(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("K_SERVICE", raising=False)


def _auth_on_values(index_dir: Path) -> dict[str, Any]:
    return {
        "artifact_dir": index_dir,
        "guides_web_base": WEB_BASE,
        "auth_mode": "on",
        "mcp_public_base_url": PUBLIC_BASE_URL,
        "google_client_id": FAKE_CLIENT_ID,
        "google_client_secret": FAKE_CLIENT_SECRET,
        "oauth_jwt_signing_key": FAKE_SIGNING_KEY,
        "bot_sa_emails": frozenset({BOT_EMAIL}),
    }


@pytest.fixture
async def open_client(server: FastMCP) -> AsyncIterator[httpx2.AsyncClient]:
    app = build_app(server)
    async with app.router.lifespan_context(app):
        transport = httpx2.ASGITransport(app=app)
        async with httpx2.AsyncClient(transport=transport, base_url="http://localhost") as http:
            yield http


def test_auth_off_builds_no_provider_and_warns_once(
    settings: McpSettings, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.DEBUG, logger="buddy_mcp.auth"):
        assert build_auth(settings, storage=MemoryStore()) is None
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert "AUTH_MODE=off" in warnings[0].getMessage()


async def test_auth_off_serves_tools_without_a_token(open_client: httpx2.AsyncClient) -> None:
    body = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
    response = await open_client.post("/mcp", json=body, headers=_HEADERS)
    assert response.status_code == 200
    assert response.json()["result"]["tools"]


def test_auth_off_is_refused_on_cloud_run(index_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("K_SERVICE", "digitiamo-buddy")
    with pytest.raises(ValidationError) as raised:
        McpSettings(artifact_dir=index_dir, guides_web_base=WEB_BASE, auth_mode="off")
    assert "AUTH_MODE" in str(raised.value)
    assert "K_SERVICE" in str(raised.value)


def test_auth_off_from_the_environment_is_refused_on_cloud_run(
    index_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ARTIFACT_DIR", str(index_dir))
    monkeypatch.setenv("GUIDES_WEB_BASE", WEB_BASE)
    monkeypatch.setenv("AUTH_MODE", "off")
    monkeypatch.setenv("K_SERVICE", "digitiamo-buddy")
    with pytest.raises(ValidationError, match="K_SERVICE"):
        McpSettings()


def test_auth_on_builds_on_cloud_run(index_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("K_SERVICE", "digitiamo-buddy")
    assert McpSettings(**_auth_on_values(index_dir)).auth_mode == "on"


def test_auth_off_builds_outside_cloud_run(index_dir: Path) -> None:
    config = McpSettings(artifact_dir=index_dir, guides_web_base=WEB_BASE, auth_mode="off")
    assert config.auth_mode == "off"
