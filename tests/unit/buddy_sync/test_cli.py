"""CLI behaviour: exit codes, subcommand output and hygiene (no secrets on stdout or stderr)."""

import json
import logging
import shutil
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

import pytest
from tests.unit.buddy_core.conftest import FakeBucket

from buddy_sync.chunker import heading_outline
from buddy_sync.cli import main
from buddy_sync.guides import select_guide_files
from buddy_sync.guides_index import GUIDES_INDEX_NAME, parse_guides_index, write_guides_index

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"
BODY_SECRETS = ("Wf9-synthetic-wifi-value", "Zq9-synthetic-not-real")
RepoFactory = Callable[[Mapping[str, str] | Path], Path]


@dataclass
class Cli:
    """Runs ``main`` and records everything it prints; no body secret may reach the output."""

    capsys: pytest.CaptureFixture[str]
    output: list[str]

    def __call__(self, *argv: str) -> tuple[int, str, str]:
        code = main(list(argv))
        captured = self.capsys.readouterr()
        self.output.extend([captured.out, captured.err])
        for secret in BODY_SECRETS:
            assert (secret in captured.out) is False
            assert (secret in captured.err) is False
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
    """Point the environment at fixture handbook and Guides repos; return the artifact dir."""

    def setup(*, rename_in_index: str | None = None) -> Path:
        repo = git_repo_factory(_tree(tmp_path, rename_in_index=rename_in_index))
        handbook = tmp_path / "handbook"
        shutil.copytree(FIXTURES / "handbook", handbook)
        for name, value in {
            "HANDBOOK_DIR": str(handbook),
            "REDACT_PAGE_FILES": "04-rete-ospiti.md",
            "GUIDES_REPO_URL": str(repo),
            "GUIDES_BRANCH": "master",
            "GUIDES_CHECKOUT_DIR": str(tmp_path / "checkout"),
            "ARTIFACT_DIR": str(tmp_path / "artifacts"),
        }.items():
            monkeypatch.setenv(name, value)
        return tmp_path / "artifacts"

    return setup


@pytest.fixture
def cli(capsys: pytest.CaptureFixture[str], caplog: pytest.LogCaptureFixture) -> Cli:
    caplog.set_level(logging.INFO)
    return Cli(capsys, [])


def test_no_subcommand_unknown_subcommand_and_removed_list_pages_return_2(cli: Cli) -> None:
    assert cli()[0] == 2
    assert cli("frobnicate")[0] == 2
    assert cli("list-pages")[0] == 2


def _error_lines(err: str) -> list[str]:
    return [line for line in err.splitlines() if line.startswith("ERROR")]


def test_run_with_empty_denylist_fails_and_names_the_variable(
    cli: Cli, env: Callable[..., Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    env()
    monkeypatch.setenv("REDACT_PAGE_FILES", "")
    code, _out, err = cli("run")
    assert code == 1
    (line,) = _error_lines(err)
    assert "REDACT_PAGE_FILES" in line


def test_run_with_empty_denylist_succeeds_when_allowed(
    cli: Cli, env: Callable[..., Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    env()
    monkeypatch.setenv("REDACT_PAGE_FILES", "")
    code, out, _err = cli("run", "--allow-empty-denylist")
    assert code == 0
    report = json.loads(out)
    assert report["pages_denied"] == 0
    assert report["pages_processed"] == 4


def test_run_without_handbook_dir_fails_and_names_the_variable(
    cli: Cli, env: Callable[..., Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    env()
    monkeypatch.delenv("HANDBOOK_DIR")
    code, _out, err = cli("run")
    assert code == 1
    (line,) = _error_lines(err)
    assert "HANDBOOK_DIR" in line


def test_run_with_a_missing_handbook_directory_reports_one_error_line(
    cli: Cli, env: Callable[..., Path], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    env()
    monkeypatch.setenv("HANDBOOK_DIR", str(tmp_path / "absent"))
    code, _out, err = cli("run")
    assert code == 1
    (line,) = _error_lines(err)
    assert line.startswith("ERROR buddy_sync HandbookFilesError")


def test_run_with_a_denylist_entry_naming_no_file_fails(
    cli: Cli, env: Callable[..., Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    artifact_dir = env()
    monkeypatch.setenv("REDACT_PAGE_FILES", "04-rete-ospiti.md,07-wi-fi.md")
    code, _out, err = cli("run")
    assert code == 1
    (line,) = _error_lines(err)
    assert "HandbookFilesError" in line
    assert not (artifact_dir / "index.db").exists()


def test_run_with_an_invalid_denylist_entry_names_the_variable_not_the_value(
    cli: Cli, env: Callable[..., Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    env()
    monkeypatch.setenv("REDACT_PAGE_FILES", "bad entry value.md")
    code, _out, err = cli("run")
    assert code == 1
    assert "REDACT_PAGE_FILES" in err
    assert ("bad entry value" in err) is False


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


def test_guides_index_writes_a_file_the_parser_reads_back(
    cli: Cli, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for name in ("HANDBOOK_DIR", "REDACT_PAGE_FILES", "ARTIFACT_DIR"):
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


# --- token file credentials (04-24, WR-03) -----------------------------------------------------


class _TokenFileWiring:
    """Stands in for the two seams the CLI reads: the token-file client factory and GcsBucket."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.factory_calls: list[tuple[Path, str | None]] = []
        self.buckets: list[tuple[str, object]] = []
        self.client_factory: Callable[[], object] = lambda: object()
        monkeypatch.setattr("buddy_sync.cli.token_file_client_factory", self._token_factory)
        monkeypatch.setattr("buddy_sync.cli.GcsBucket", self._gcs_bucket)

    def _token_factory(self, token_file: Path, project: str | None) -> Callable[[], object]:
        self.factory_calls.append((token_file, project))
        return self.client_factory

    def _gcs_bucket(
        self, name: str, *, client_factory: Callable[[], object] | None = None
    ) -> FakeBucket:
        self.buckets.append((name, client_factory))
        return FakeBucket()


@pytest.fixture
def wiring(monkeypatch: pytest.MonkeyPatch) -> _TokenFileWiring:
    return _TokenFileWiring(monkeypatch)


def _publish_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ARTIFACT_DIR", str(tmp_path / "artifacts"))
    monkeypatch.setenv("ARTIFACT_BUCKET", "demo-ai-buddy-index")
    monkeypatch.setattr(
        "buddy_sync.cli.publish_index",
        lambda *_args, **_kwargs: type("R", (), {"status": "published", "build_id": "b1"})(),
    )


def test_publish_uses_the_token_file_when_set(
    wiring: _TokenFileWiring, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _publish_env(monkeypatch, tmp_path)
    monkeypatch.setenv("GCS_ACCESS_TOKEN_FILE", str(tmp_path / "token"))
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "demo-project")

    assert main(["publish"]) == 0

    assert wiring.factory_calls == [(tmp_path / "token", "demo-project")]
    assert wiring.buckets == [("demo-ai-buddy-index", wiring.client_factory)]


def test_publish_without_a_token_file_keeps_the_default_bucket(
    wiring: _TokenFileWiring, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _publish_env(monkeypatch, tmp_path)
    monkeypatch.delenv("GCS_ACCESS_TOKEN_FILE", raising=False)

    assert main(["publish"]) == 0

    assert wiring.factory_calls == []
    assert wiring.buckets == [("demo-ai-buddy-index", None)]


def test_upload_videos_uses_the_token_file_when_set(
    wiring: _TokenFileWiring, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    guides = tmp_path / "guides"
    guides.mkdir()
    (guides / "README.md").write_text("# Guides\n", encoding="utf-8")
    monkeypatch.setenv("VIDEO_BUCKET", "demo-ai-buddy-videos")
    monkeypatch.setenv("GCS_ACCESS_TOKEN_FILE", str(tmp_path / "token"))
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)

    code = main(["upload-videos", "--guides-dir", str(guides), "--videos-dir", str(tmp_path)])

    assert code == 0
    assert wiring.factory_calls == [(tmp_path / "token", None)]
    assert wiring.buckets == [("demo-ai-buddy-videos", wiring.client_factory)]


def test_an_injected_bucket_factory_wins_over_the_token_file(
    wiring: _TokenFileWiring, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _publish_env(monkeypatch, tmp_path)
    monkeypatch.setenv("GCS_ACCESS_TOKEN_FILE", str(tmp_path / "token"))
    chosen = FakeBucket()

    assert main(["publish"], bucket_factory=lambda _name: chosen) == 0

    assert wiring.buckets == []
