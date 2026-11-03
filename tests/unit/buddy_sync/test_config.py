"""SyncSettings: env loading, secret masking, list parsing and validators."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from buddy_sync.config import ConfigError, SyncSettings

ENV_EXAMPLE = Path(__file__).resolve().parents[3] / ".env.example"
SENTINEL = "pk_SYNTHETIC_TOKEN_DO_NOT_USE_0000000000"


def _example_env() -> dict[str, str]:
    values: dict[str, str] = {}
    for line in ENV_EXAMPLE.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        key, _, value = stripped.partition("=")
        values[key] = value
    return values


@pytest.fixture
def example_env(monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    """Environment equal to .env.example, with any host values for these keys cleared."""
    values = _example_env()
    for key, value in values.items():
        monkeypatch.setenv(key, value)
    return values


def test_settings_validate_from_env_example(example_env: dict[str, str]) -> None:
    s = SyncSettings()
    assert s.clickup_doc_id == example_env["CLICKUP_DOC_ID"]
    assert s.guides_branch == "master"
    assert s.redact_email_allow_domains == frozenset({"digitiamo.com"})
    assert s.redact_page_ids == frozenset()
    assert s.clickup_token is None
    assert s.clickup_workspace_id is None


def test_clickup_token_never_appears_in_repr_str_or_json(
    example_env: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CLICKUP_TOKEN", SENTINEL)
    monkeypatch.setenv("GUIDES_REPO_TOKEN", SENTINEL)
    s = SyncSettings()
    assert s.clickup_token is not None
    assert s.clickup_token.get_secret_value() == SENTINEL
    assert (SENTINEL in repr(s)) is False
    assert (SENTINEL in str(s)) is False
    assert (SENTINEL in s.model_dump_json()) is False


def test_page_ids_and_domains_parse_comma_separated(
    example_env: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("REDACT_PAGE_IDS", "a-1, b-2")
    monkeypatch.setenv("REDACT_EMAIL_ALLOW_DOMAINS", " Digitiamo.com ,, Example.Invalid ")
    s = SyncSettings()
    assert s.redact_page_ids == frozenset({"a-1", "b-2"})
    assert s.redact_email_allow_domains == frozenset({"digitiamo.com", "example.invalid"})


@pytest.mark.parametrize("branch", ["--upload-pack=x", "-x", "bad branch", "a;b"])
def test_guides_branch_rejects_option_like_values(
    example_env: dict[str, str], monkeypatch: pytest.MonkeyPatch, branch: str
) -> None:
    monkeypatch.setenv("GUIDES_BRANCH", branch)
    with pytest.raises(ValidationError) as excinfo:
        SyncSettings()
    assert (branch in str(excinfo.value)) is False


def test_clickup_doc_id_rejects_unexpected_characters(
    example_env: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CLICKUP_DOC_ID", "abc/../x")
    with pytest.raises(ValidationError):
        SyncSettings()


def test_require_clickup_names_missing_variables(example_env: dict[str, str]) -> None:
    s = SyncSettings()
    with pytest.raises(ConfigError) as excinfo:
        s.require_clickup()
    message = str(excinfo.value)
    assert "CLICKUP_TOKEN" in message
    assert "CLICKUP_WORKSPACE_ID" in message


def test_require_clickup_returns_token_and_workspace(
    example_env: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CLICKUP_TOKEN", SENTINEL)
    monkeypatch.setenv("CLICKUP_WORKSPACE_ID", "123456")
    token, workspace_id = SyncSettings().require_clickup()
    assert token.get_secret_value() == SENTINEL
    assert workspace_id == 123456
