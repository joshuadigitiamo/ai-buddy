"""McpSettings hygiene: errors name variables, never secret values; bounds on the new knobs."""

from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError
from tests.unit.mcp_server.conftest import (
    FAKE_CLIENT_ID,
    FAKE_CLIENT_SECRET,
    FAKE_SIGNING_KEY,
    PUBLIC_BASE_URL,
    WEB_BASE,
)

from buddy_mcp.config import McpSettings

_ENV_VARIABLES = (
    "ARTIFACT_DIR",
    "GUIDES_WEB_BASE",
    "MCP_HOST",
    "PORT",
    "GAP_TTL_DAYS",
    "GAP_COLLECTION",
    "AUTH_MODE",
    "MCP_PUBLIC_BASE_URL",
    "GOOGLE_CLIENT_ID",
    "GOOGLE_CLIENT_SECRET",
    "OAUTH_JWT_SIGNING_KEY",
    "ALLOWED_EMAIL_DOMAIN",
    "BOT_SA_EMAILS",
    "OAUTH_STORAGE",
    "OAUTH_STORAGE_ENCRYPTION_KEY",
    "OAUTH_COLLECTION",
    "RATE_LIMIT_RPS",
    "RATE_LIMIT_BURST",
    "K_SERVICE",
)

_SECRET_FIELDS = {
    "GOOGLE_CLIENT_SECRET": "google_client_secret",
    "OAUTH_JWT_SIGNING_KEY": "oauth_jwt_signing_key",
}


@pytest.fixture(autouse=True)
def _clean_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """run-unit-tests.sh loads an env file into the container; start from nothing."""
    for name in _ENV_VARIABLES:
        monkeypatch.delenv(name, raising=False)


def _values(index_dir: Path, **overrides: Any) -> dict[str, Any]:
    values: dict[str, Any] = {
        "artifact_dir": index_dir,
        "guides_web_base": WEB_BASE,
        "auth_mode": "on",
        "mcp_public_base_url": PUBLIC_BASE_URL,
        "google_client_id": FAKE_CLIENT_ID,
        "google_client_secret": FAKE_CLIENT_SECRET,
        "oauth_jwt_signing_key": FAKE_SIGNING_KEY,
    }
    values.update(overrides)
    return {key: value for key, value in values.items() if value is not None}


@pytest.mark.parametrize(
    ("variable", "field"),
    [
        ("MCP_PUBLIC_BASE_URL", "mcp_public_base_url"),
        ("GOOGLE_CLIENT_ID", "google_client_id"),
        ("GOOGLE_CLIENT_SECRET", "google_client_secret"),
        ("OAUTH_JWT_SIGNING_KEY", "oauth_jwt_signing_key"),
    ],
)
def test_auth_on_names_the_missing_variable(index_dir: Path, variable: str, field: str) -> None:
    with pytest.raises(ValidationError) as raised:
        McpSettings(**_values(index_dir, **{field: None}))
    assert variable in str(raised.value)


def test_auth_on_lists_every_missing_variable(index_dir: Path) -> None:
    with pytest.raises(ValidationError) as raised:
        McpSettings(artifact_dir=index_dir, guides_web_base=WEB_BASE)
    for variable in ("MCP_PUBLIC_BASE_URL", "GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET"):
        assert variable in str(raised.value)


def test_auth_off_needs_none_of_the_auth_variables(index_dir: Path) -> None:
    config = McpSettings(artifact_dir=index_dir, guides_web_base=WEB_BASE, auth_mode="off")
    assert config.google_client_secret is None


def test_secret_values_never_reach_errors_or_repr(index_dir: Path) -> None:
    sentinel = "sentinel-secret-9f3a1c"
    values = _values(
        index_dir,
        google_client_secret=sentinel,
        oauth_jwt_signing_key=sentinel + "-key",
        oauth_storage_encryption_key=sentinel + "-fernet",
    )
    config = McpSettings(**values)
    assert sentinel not in repr(config)
    assert sentinel not in str(config)
    for broken in ({"oauth_storage": "file"}, {"mcp_public_base_url": "http://example.com"}):
        with pytest.raises(ValidationError) as raised:
            McpSettings(**{**values, **broken})
        assert sentinel not in str(raised.value)
        assert sentinel not in repr(raised.value)


@pytest.mark.parametrize("secret_name", sorted(_SECRET_FIELDS))
def test_secret_is_read_from_the_environment_without_leaking(
    index_dir: Path, monkeypatch: pytest.MonkeyPatch, secret_name: str
) -> None:
    sentinel = "env-sentinel-77be02"
    monkeypatch.setenv(secret_name, sentinel)
    monkeypatch.setenv("OAUTH_STORAGE", "bogus")
    with pytest.raises(ValidationError) as raised:
        McpSettings(**_values(index_dir, **{_SECRET_FIELDS[secret_name]: None}))
    assert sentinel not in str(raised.value)


def test_firestore_storage_requires_the_encryption_key(index_dir: Path) -> None:
    with pytest.raises(ValidationError) as raised:
        McpSettings(**_values(index_dir, oauth_storage="firestore"))
    assert "OAUTH_STORAGE_ENCRYPTION_KEY" in str(raised.value)


def test_firestore_storage_with_the_key_builds(index_dir: Path) -> None:
    config = McpSettings(
        **_values(index_dir, oauth_storage="firestore", oauth_storage_encryption_key="k" * 44)
    )
    assert config.oauth_storage == "firestore"


@pytest.mark.parametrize("kind", ["file", "disk", "FILE"])
def test_oauth_storage_accepts_only_memory_or_firestore(index_dir: Path, kind: str) -> None:
    with pytest.raises(ValidationError, match="oauth_storage"):
        McpSettings(**_values(index_dir, oauth_storage=kind))


def test_oauth_storage_defaults_to_memory(index_dir: Path) -> None:
    assert McpSettings(**_values(index_dir)).oauth_storage == "memory"


@pytest.mark.parametrize(
    ("url", "accepted"),
    [
        ("http://example.com", False),
        ("ftp://buddy.example", False),
        ("buddy.example", False),
        ("http://localhost:8000", True),
        ("http://127.0.0.1:8000", True),
        ("https://buddy.example", True),
    ],
)
def test_public_base_url_scheme_rule(index_dir: Path, url: str, accepted: bool) -> None:
    if accepted:
        assert McpSettings(**_values(index_dir, mcp_public_base_url=url)).mcp_public_base_url
    else:
        with pytest.raises(ValidationError, match="mcp_public_base_url"):
            McpSettings(**_values(index_dir, mcp_public_base_url=url))


def test_public_base_url_loses_its_trailing_slash(index_dir: Path) -> None:
    config = McpSettings(**_values(index_dir, mcp_public_base_url="https://buddy.example/"))
    assert config.mcp_public_base_url == "https://buddy.example"


def test_bot_sa_emails_are_split_and_lowercased(
    index_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(
        "BOT_SA_EMAILS", "A@x.iam.gserviceaccount.com, b@y.iam.gserviceaccount.com ,"
    )
    config = McpSettings(**_values(index_dir))
    assert config.bot_sa_emails == frozenset(
        {"a@x.iam.gserviceaccount.com", "b@y.iam.gserviceaccount.com"}
    )


def test_bot_sa_emails_default_is_empty(index_dir: Path) -> None:
    assert McpSettings(**_values(index_dir)).bot_sa_emails == frozenset()


def test_allowed_email_domain_defaults_and_is_normalized(index_dir: Path) -> None:
    assert McpSettings(**_values(index_dir)).allowed_email_domain == "digitiamo.com"
    config = McpSettings(**_values(index_dir, allowed_email_domain=" Example.COM "))
    assert config.allowed_email_domain == "example.com"
    with pytest.raises(ValidationError, match="allowed_email_domain"):
        McpSettings(**_values(index_dir, allowed_email_domain="a@example.com"))


@pytest.mark.parametrize("rps", [0, -1, -0.5])
def test_rate_limit_rps_must_be_positive(index_dir: Path, rps: float) -> None:
    with pytest.raises(ValidationError, match="rate_limit_rps"):
        McpSettings(**_values(index_dir, rate_limit_rps=rps))


@pytest.mark.parametrize("burst", [0, -3])
def test_rate_limit_burst_must_be_at_least_one(index_dir: Path, burst: int) -> None:
    with pytest.raises(ValidationError, match="rate_limit_burst"):
        McpSettings(**_values(index_dir, rate_limit_burst=burst))


def test_rate_limit_defaults(index_dir: Path) -> None:
    config = McpSettings(**_values(index_dir))
    assert config.rate_limit_rps == 5.0
    assert config.rate_limit_burst == 30


def test_rate_limit_from_the_environment(index_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RATE_LIMIT_RPS", "2.5")
    monkeypatch.setenv("RATE_LIMIT_BURST", "7")
    config = McpSettings(**_values(index_dir))
    assert (config.rate_limit_rps, config.rate_limit_burst) == (2.5, 7)
