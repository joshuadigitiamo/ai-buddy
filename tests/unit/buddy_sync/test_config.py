"""SyncSettings: env loading, list parsing and validators."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from buddy_sync.config import SyncSettings

ENV_EXAMPLE = Path(__file__).resolve().parents[3] / ".env.example"


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
    assert s.handbook_dir == Path("/handbook")
    assert s.redact_page_files == frozenset()
    assert s.guides_repo_url == "/guides-src"
    assert s.guides_branch == "master"
    assert s.redact_email_allow_domains == frozenset({"digitiamo.com"})


def test_settings_hold_exactly_the_documented_fields() -> None:
    assert set(SyncSettings.model_fields) == {
        "handbook_dir",
        "redact_page_files",
        "redact_email_allow_domains",
        "guides_repo_url",
        "guides_branch",
        "guides_checkout_dir",
        "artifact_dir",
    }


def test_page_files_and_domains_parse_comma_separated(
    example_env: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("REDACT_PAGE_FILES", "a.md, b.md")
    monkeypatch.setenv("REDACT_EMAIL_ALLOW_DOMAINS", " Digitiamo.com ,, Example.Invalid ")
    s = SyncSettings()
    assert s.redact_page_files == frozenset({"a.md", "b.md"})
    assert s.redact_email_allow_domains == frozenset({"digitiamo.com", "example.invalid"})


@pytest.mark.parametrize(
    "entry", ["sub/a.md", "../a.md", "a b.md", "a.txt", "plainname", "/etc/a.md", "-a.md"]
)
def test_page_file_entries_must_be_bare_md_names(
    example_env: dict[str, str], monkeypatch: pytest.MonkeyPatch, entry: str
) -> None:
    monkeypatch.setenv("REDACT_PAGE_FILES", f"ok.md,{entry}")
    with pytest.raises(ValidationError) as excinfo:
        SyncSettings()
    message = str(excinfo.value)
    assert "redact_page_files" in message
    assert (entry in message) is False


def test_missing_handbook_dir_names_the_field(
    example_env: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("HANDBOOK_DIR")
    with pytest.raises(ValidationError) as excinfo:
        SyncSettings()
    assert "handbook_dir" in str(excinfo.value)


@pytest.mark.parametrize("branch", ["--upload-pack=x", "-x", "bad branch", "a;b"])
def test_guides_branch_rejects_option_like_values(
    example_env: dict[str, str], monkeypatch: pytest.MonkeyPatch, branch: str
) -> None:
    monkeypatch.setenv("GUIDES_BRANCH", branch)
    with pytest.raises(ValidationError) as excinfo:
        SyncSettings()
    assert (branch in str(excinfo.value)) is False
