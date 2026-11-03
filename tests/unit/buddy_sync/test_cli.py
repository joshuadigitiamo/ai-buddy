"""CLI behaviour: exit codes, subcommand output and hygiene (no secrets on stdout or stderr)."""

import json
import logging
import shutil
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
import pytest

from buddy_sync.chunker import heading_outline
from buddy_sync.cli import main
from buddy_sync.guides import select_guide_files
from buddy_sync.guides_index import GUIDES_INDEX_NAME, parse_guides_index, write_guides_index

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"
TOKEN = "tok-synthetic-Kd8-not-a-real-token"
BODY_SECRETS = ("Wf9-synthetic-wifi-value", "Zq9-synthetic-not-real")
RepoFactory = Callable[[Mapping[str, str] | Path], Path]


@dataclass
class Cli:
    """Runs ``main`` against the mock ClickUp transport and records everything it prints."""

    transport: httpx.MockTransport
    capsys: pytest.CaptureFixture[str]
    output: list[str]

    def __call__(self, *argv: str) -> tuple[int, str, str]:
        code = main(list(argv), transport=self.transport)
        captured = self.capsys.readouterr()
        self.output.extend([captured.out, captured.err])
        assert TOKEN not in captured.out
        assert TOKEN not in captured.err
        return code, captured.out, captured.err


def _tree(tmp_path: Path, *, rename_in_index: str | None = None) -> Path:
    tree = tmp_path / "guides-tree"
    shutil.copytree(FIXTURES / "guides_repo", tree)
    shutil.copy(FIXTURES / "guides_videos" / "README.md", tree / "README.md")
    shutil.copytree(FIXTURES / "guides_videos" / "videos" / "demo", tree / "videos" / "demo")
    outline = {
        relpath: heading_outline((tree / relpath).read_text(encoding="utf-8"))
        for relpath in select_guide_files(tree)
    }
    index = write_guides_index(tree, outline)
    if rename_in_index is not None:
        index.write_text(
            index.read_text(encoding="utf-8").replace(rename_in_index, "Renamed section"),
            encoding="utf-8",
        )
    return tree


@pytest.fixture
def env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, git_repo_factory: RepoFactory
) -> Callable[..., Path]:
    """Point the process environment at a fixture Guides repo; returns the artifact dir."""

    def setup(*, rename_in_index: str | None = None) -> Path:
        repo = git_repo_factory(_tree(tmp_path, rename_in_index=rename_in_index))
        for name, value in {
            "CLICKUP_TOKEN": TOKEN,
            "CLICKUP_WORKSPACE_ID": "123",
            "CLICKUP_DOC_ID": "demo-doc",
            "REDACT_PAGE_IDS": "demo-page-wifi",
            "GUIDES_REPO_URL": str(repo),
            "GUIDES_BRANCH": "master",
            "GUIDES_CHECKOUT_DIR": str(tmp_path / "checkout"),
            "ARTIFACT_DIR": str(tmp_path / "artifacts"),
        }.items():
            monkeypatch.setenv(name, value)
        monkeypatch.delenv("GUIDES_REPO_TOKEN", raising=False)
        return tmp_path / "artifacts"

    return setup


@pytest.fixture
def cli(capsys: pytest.CaptureFixture[str], caplog: pytest.LogCaptureFixture) -> Cli:
    payload: list[dict[str, Any]] = json.loads(
        (FIXTURES / "clickup" / "pages.json").read_text(encoding="utf-8")
    )

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    caplog.set_level(logging.INFO)
    return Cli(httpx.MockTransport(handler), capsys, [])


def test_no_subcommand_and_unknown_subcommand_return_2(cli: Cli) -> None:
    assert cli()[0] == 2
    assert cli("frobnicate")[0] == 2


def test_run_with_empty_denylist_fails_and_names_the_variable(
    cli: Cli, env: Callable[..., Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    env()
    monkeypatch.setenv("REDACT_PAGE_IDS", "")
    code, _out, err = cli("run")
    assert code == 1
    assert "ERROR" in err
    assert "REDACT_PAGE_IDS" in err


def test_run_with_empty_denylist_succeeds_when_allowed(
    cli: Cli, env: Callable[..., Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    env()
    monkeypatch.setenv("REDACT_PAGE_IDS", "")
    code, out, _err = cli("run", "--allow-empty-denylist")
    assert code == 0
    assert json.loads(out)["pages_denied"] == 0


def test_run_without_token_fails_and_names_the_variable(
    cli: Cli, env: Callable[..., Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    env()
    monkeypatch.delenv("CLICKUP_TOKEN")
    code, _out, err = cli("run")
    assert code == 1
    assert "ERROR" in err
    assert "CLICKUP_TOKEN" in err


def test_run_with_invalid_settings_names_the_variable_not_its_value(
    cli: Cli, env: Callable[..., Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    env()
    monkeypatch.setenv("CLICKUP_DOC_ID", "bad doc id")
    code, _out, err = cli("run")
    assert code == 1
    assert "CLICKUP_DOC_ID" in err
    assert "bad doc id" not in err


def test_strict_fails_on_guides_index_drift_and_lenient_run_logs_it(
    cli: Cli, env: Callable[..., Path], caplog: pytest.LogCaptureFixture
) -> None:
    artifact_dir = env(rename_in_index="Chunking")
    code, _out, err = cli("run", "--strict")
    assert code == 1
    assert "drift" in err
    assert not (artifact_dir / "index.db").exists()

    code, out, _err = cli("run")
    assert code == 0
    assert json.loads(out)["guides_index_drift"] >= 1
    assert "guides_index drift" in caplog.text


def test_list_pages_prints_ids_and_redacted_titles_only(cli: Cli, env: Callable[..., Path]) -> None:
    env()
    code, out, _err = cli("list-pages")
    assert code == 0
    lines = out.splitlines()
    assert "demo-page-0001\tHandbook Demo" in lines
    assert "demo-page-0002\t  Benvenuto" in lines
    assert any(line.startswith("demo-page-wifi\t") and line.endswith("[denied]") for line in lines)
    assert not any("[denied]" in line for line in lines if "demo-page-wifi" not in line)
    for secret in BODY_SECRETS:
        assert secret not in out


def test_guides_index_writes_a_file_the_parser_reads_back(
    cli: Cli, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for name in ("CLICKUP_TOKEN", "CLICKUP_WORKSPACE_ID", "CLICKUP_DOC_ID", "ARTIFACT_DIR"):
        monkeypatch.delenv(name, raising=False)
    tree = tmp_path / "plain-tree"
    shutil.copytree(FIXTURES / "guides_repo", tree)
    code, out, _err = cli("guides-index", "--checkout", str(tree))
    assert code == 0
    assert str(tree / GUIDES_INDEX_NAME) in out
    entries = parse_guides_index((tree / GUIDES_INDEX_NAME).read_text(encoding="utf-8"))
    expected = {
        (relpath, heading.level, heading.title, heading.line)
        for relpath in select_guide_files(tree)
        for heading in heading_outline((tree / relpath).read_text(encoding="utf-8"))
    }
    assert expected
    assert {(e.file, e.level, e.title, e.line) for e in entries} == expected


def test_search_accepts_punctuation_and_reports_a_missing_artifact(
    cli: Cli, env: Callable[..., Path], tmp_path: Path
) -> None:
    artifact_dir = env()
    assert cli("run")[0] == 0
    code, out, _err = cli("search", "what: is-this?", "--artifact-dir", str(artifact_dir))
    assert code == 0
    assert TOKEN not in out

    code, out, err = cli("search", "x", "--artifact-dir", str(tmp_path / "empty"))
    assert code == 1
    assert "ERROR" in err
    assert out == ""


def test_search_lines_carry_location_headings_and_video_link(
    cli: Cli, env: Callable[..., Path]
) -> None:
    artifact_dir = env()
    assert cli("run")[0] == 0
    code, out, _err = cli("search", "chunking", "--limit", "1", "--artifact-dir", str(artifact_dir))
    assert code == 0
    (line,) = out.splitlines()
    location, headings, link = line.split("  ")
    assert location.startswith("AI-Engineering/DEMO_GUIDE.md:")
    assert headings == "1. Basics > Chunking"
    assert link.endswith("#t=30")


def test_search_uses_artifact_dir_from_environment(
    cli: Cli, env: Callable[..., Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    artifact_dir = env()
    assert cli("run")[0] == 0
    monkeypatch.setenv("ARTIFACT_DIR", str(artifact_dir))
    code, out, _err = cli("search", "chunking")
    assert code == 0
    assert "DEMO_GUIDE.md" in out
