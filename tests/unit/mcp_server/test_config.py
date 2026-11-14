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
    "ARTIFACT_STORE",
    "ARTIFACT_BUCKET",
    "ARTIFACT_PREFIX",
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
    "MCP_ALLOWED_HOSTS",
    "DEPLOY_ENV",
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
    config = McpSettings(**_off_values(index_dir, deploy_env="local"))
    assert config.google_client_secret is None


def test_secret_values_never_reach_errors_or_repr(index_dir: Path) -> None:
    sentinel = "sentinel-secret-9f3a1c"
    values = _values(
        index_dir,
        google_client_secret=sentinel,
        oauth_jwt_signing_key=sentinel + "-key-" + "x" * 16,
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
        ("http://localhost.evil.example", False),
        ("http://127.0.0.1.evil.example", False),
        ("http://localhost@evil.example", False),
        ("http://", False),
        ("https://", False),
        ("https://mcp.example.invalid", True),
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


@pytest.mark.parametrize(
    "value", ["http://x", "x:8000", "*.svc", "mcp_server", "a..b", "x/y", "-x", "x-", "UP per"]
)
def test_mcp_allowed_hosts_refuses_anything_but_a_bare_hostname(
    index_dir: Path, value: str
) -> None:
    with pytest.raises(ValidationError) as raised:
        McpSettings(**_values(index_dir, mcp_allowed_hosts=value))
    text = str(raised.value)
    assert "mcp_allowed_hosts" in text.lower()
    assert value not in text


def test_mcp_allowed_hosts_is_split_and_lowercased_from_the_environment(
    index_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MCP_ALLOWED_HOSTS", " MCP-Server, buddy.svc.cluster.local ,")
    config = McpSettings(**_values(index_dir))
    assert config.mcp_allowed_hosts == frozenset({"mcp-server", "buddy.svc.cluster.local"})


def test_mcp_allowed_hosts_defaults_to_empty(index_dir: Path) -> None:
    assert McpSettings(**_values(index_dir)).mcp_allowed_hosts == frozenset()


# --- DEPLOY_ENV: the explicit marker that makes auth-off fail closed (INFRA-01) --------------


def _off_values(index_dir: Path, **overrides: Any) -> dict[str, Any]:
    return {"artifact_dir": index_dir, "guides_web_base": WEB_BASE, "auth_mode": "off", **overrides}


def test_deploy_env_defaults_to_production(index_dir: Path) -> None:
    assert McpSettings(**_values(index_dir)).deploy_env == "production"


def test_deploy_env_empty_means_production(
    index_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DEPLOY_ENV", "")
    assert McpSettings(**_values(index_dir)).deploy_env == "production"
    with pytest.raises(ValidationError, match="DEPLOY_ENV"):
        McpSettings(**_off_values(index_dir))


def test_deploy_env_production_refuses_auth_off_naming_both_variables(index_dir: Path) -> None:
    with pytest.raises(ValidationError) as raised:
        McpSettings(**_off_values(index_dir, deploy_env="production"))
    assert "AUTH_MODE" in str(raised.value)
    assert "DEPLOY_ENV" in str(raised.value)


def test_deploy_env_local_accepts_auth_off(index_dir: Path) -> None:
    config = McpSettings(**_off_values(index_dir, deploy_env="local"))
    assert (config.auth_mode, config.deploy_env) == ("off", "local")


@pytest.mark.parametrize("auth_mode", ["on", "off"])
def test_deploy_env_local_is_refused_when_k_service_is_set(
    index_dir: Path, monkeypatch: pytest.MonkeyPatch, auth_mode: str
) -> None:
    monkeypatch.setenv("K_SERVICE", "digitiamo-buddy")
    with pytest.raises(ValidationError) as raised:
        McpSettings(**_values(index_dir, auth_mode=auth_mode, deploy_env="local"))
    assert "DEPLOY_ENV" in str(raised.value)
    assert "K_SERVICE" in str(raised.value)


@pytest.mark.parametrize("k_service", [None, "digitiamo-buddy"])
@pytest.mark.parametrize("deploy_env", ["production", "prod", "staging", "LOCAL", "kind", "dev"])
def test_every_value_but_local_refuses_auth_off(
    index_dir: Path, monkeypatch: pytest.MonkeyPatch, deploy_env: str, k_service: str | None
) -> None:
    """Invariant: auth-off is accepted for DEPLOY_ENV=local only, with and without K_SERVICE."""
    if k_service:
        monkeypatch.setenv("K_SERVICE", k_service)
    monkeypatch.setenv("DEPLOY_ENV", deploy_env)
    with pytest.raises(ValidationError):
        McpSettings(**_off_values(index_dir))


def test_deploy_env_is_read_from_the_environment(
    index_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DEPLOY_ENV", "local")
    assert McpSettings(**_off_values(index_dir)).deploy_env == "local"


@pytest.mark.parametrize("url", ["http://localhost:8000", "https://mcp.example.invalid"])
def test_public_base_url_accepts_loopback_http_and_https(index_dir: Path, url: str) -> None:
    assert McpSettings(**_values(index_dir, mcp_public_base_url=url)).mcp_public_base_url == url


@pytest.mark.parametrize(
    "url", ["http://localhost.evil.example", "http://127.0.0.1.evil.example", "http://evil.example"]
)
def test_public_base_url_refuses_plain_http_to_lookalike_hosts(index_dir: Path, url: str) -> None:
    with pytest.raises(ValidationError, match="mcp_public_base_url"):
        McpSettings(**_values(index_dir, mcp_public_base_url=url))


def test_signing_key_shorter_than_32_characters_is_refused_without_echo(index_dir: Path) -> None:
    key = "k" * 31
    with pytest.raises(ValidationError) as raised:
        McpSettings(**_values(index_dir, oauth_jwt_signing_key=key))
    assert "OAUTH_JWT_SIGNING_KEY" in str(raised.value)
    assert key not in str(raised.value)
    assert key not in repr(raised.value)


def test_signing_key_of_32_characters_is_accepted(index_dir: Path) -> None:
    config = McpSettings(**_values(index_dir, oauth_jwt_signing_key="k" * 32))
    assert config.oauth_jwt_signing_key is not None


def test_signing_key_length_is_not_checked_when_auth_is_off(index_dir: Path) -> None:
    config = McpSettings(**_off_values(index_dir, deploy_env="local", oauth_jwt_signing_key="k"))
    assert config.auth_mode == "off"


# --- ARTIFACT_STORE: the index comes from a directory or a bucket by configuration (D-06, D-10) ---


def _gcs_values(**overrides: Any) -> dict[str, Any]:
    values: dict[str, Any] = {
        "artifact_store": "gcs",
        "artifact_bucket": "bucket-x",
        "guides_web_base": WEB_BASE,
        "auth_mode": "off",
        "deploy_env": "local",
    }
    values.update(overrides)
    return {key: value for key, value in values.items() if value is not None}


def test_artifact_store_defaults_to_local_with_no_bucket(index_dir: Path) -> None:
    config = McpSettings(**_values(index_dir))
    assert (config.artifact_store, config.artifact_bucket, config.artifact_prefix) == (
        "local",
        None,
        "",
    )


def test_gcs_store_needs_a_bucket_but_no_directory() -> None:
    config = McpSettings(**_gcs_values())
    assert (config.artifact_store, config.artifact_bucket, config.artifact_dir) == (
        "gcs",
        "bucket-x",
        None,
    )


def test_gcs_store_without_a_bucket_names_artifact_bucket() -> None:
    with pytest.raises(ValidationError) as raised:
        McpSettings(**_gcs_values(artifact_bucket=None))
    assert "ARTIFACT_BUCKET" in str(raised.value)


def test_local_store_without_a_directory_names_artifact_dir() -> None:
    with pytest.raises(ValidationError) as raised:
        McpSettings(guides_web_base=WEB_BASE, auth_mode="off", deploy_env="local")
    assert "ARTIFACT_DIR" in str(raised.value)


def test_unknown_artifact_store_is_refused(index_dir: Path) -> None:
    with pytest.raises(ValidationError, match="artifact_store"):
        McpSettings(**_values(index_dir, artifact_store="s3"))


@pytest.mark.parametrize("prefix", ["../", "/a/", "A/", "a", "a//", "a/../"])
def test_artifact_prefix_refuses_what_is_not_lowercase_slash_terminated(prefix: str) -> None:
    with pytest.raises(ValidationError) as raised:
        McpSettings(**_gcs_values(artifact_prefix=prefix))
    assert "ARTIFACT_PREFIX".lower() in str(raised.value).lower()
    assert f"'{prefix}'" not in str(raised.value)


@pytest.mark.parametrize("prefix", ["index/", "a/b/", ""])
def test_artifact_prefix_accepts_lowercase_segments(prefix: str) -> None:
    assert McpSettings(**_gcs_values(artifact_prefix=prefix)).artifact_prefix == prefix


@pytest.mark.parametrize("bucket", ["Upper", "ab", "a b c", "gs://x", "-abc", "../x"])
def test_artifact_bucket_refuses_what_is_not_a_bucket_name_without_echo(bucket: str) -> None:
    with pytest.raises(ValidationError) as raised:
        McpSettings(**_gcs_values(artifact_bucket=bucket))
    assert "artifact_bucket" in str(raised.value)
    assert f"'{bucket}'" not in str(raised.value)


def test_artifact_store_settings_are_read_from_the_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ARTIFACT_STORE", "gcs")
    monkeypatch.setenv("ARTIFACT_BUCKET", "bucket-env")
    monkeypatch.setenv("ARTIFACT_PREFIX", "idx/")
    config = McpSettings(guides_web_base=WEB_BASE, auth_mode="off", deploy_env="local")
    assert (config.artifact_store, config.artifact_bucket, config.artifact_prefix) == (
        "gcs",
        "bucket-env",
        "idx/",
    )


def test_empty_artifact_bucket_and_prefix_mean_unset(
    index_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ARTIFACT_BUCKET", "")
    monkeypatch.setenv("ARTIFACT_PREFIX", "")
    config = McpSettings(**_values(index_dir))
    assert (config.artifact_bucket, config.artifact_prefix) == (None, "")
