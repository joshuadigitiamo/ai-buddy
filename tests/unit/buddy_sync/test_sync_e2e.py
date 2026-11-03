"""End to end on fixtures: ``main(["run"])`` publishes a searchable, redacted artifact."""

import json
import logging
import os
import shutil
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

import pytest

from buddy_core.index_reader import open_index
from buddy_sync.chunker import heading_outline
from buddy_sync.cli import main
from buddy_sync.guides import select_guide_files
from buddy_sync.guides_index import write_guides_index
from buddy_sync.handbook_files import SOURCE_ID

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"
FORBIDDEN = (
    b"04-rete-ospiti",
    b"Rete ospiti",
    b"Wf9-synthetic-wifi-value",
    b"Zq9-synthetic-not-real",
    b"legacy.example.invalid",
    b"legacy-0001",
)
KEPT_IDS = ["01-benvenuto", "02-ferie", "03-accesso-ufficio"]

RepoFactory = Callable[[Mapping[str, str] | Path], Path]


def _guides_tree(tmp_path: Path) -> Path:
    tree = tmp_path / "guides-tree"
    shutil.copytree(FIXTURES / "guides_repo", tree)
    shutil.copy(FIXTURES / "guides_videos" / "README.md", tree / "README.md")
    shutil.copytree(FIXTURES / "guides_videos" / "videos" / "demo", tree / "videos" / "demo")
    outline = {
        relpath: heading_outline((tree / relpath).read_text(encoding="utf-8"))
        for relpath in select_guide_files(tree)
    }
    write_guides_index(tree, outline)
    return tree


def test_end_to_end(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
    git_repo_factory: RepoFactory,
) -> None:
    repo = git_repo_factory(_guides_tree(tmp_path))
    handbook = tmp_path / "handbook"
    shutil.copytree(FIXTURES / "handbook", handbook)
    artifact_dir = tmp_path / "artifacts"
    for name, value in {
        "HANDBOOK_DIR": str(handbook),
        "REDACT_PAGE_FILES": "04-rete-ospiti.md",
        "GUIDES_REPO_URL": str(repo),
        "GUIDES_BRANCH": "master",
        "GUIDES_CHECKOUT_DIR": str(tmp_path / "checkout"),
        "ARTIFACT_DIR": str(artifact_dir),
    }.items():
        monkeypatch.setenv(name, value)

    seen_output: list[str] = []

    def run(*argv: str) -> tuple[int, str]:
        code = main(list(argv))
        captured = capsys.readouterr()
        seen_output.extend([captured.out, captured.err])
        return code, captured.out

    def run_report(*argv: str) -> dict[str, Any]:
        code, out = run("run", *argv)
        assert code == 0
        report: dict[str, Any] = json.loads(out)
        return report

    index_db = artifact_dir / "index.db"
    caplog.set_level(logging.INFO)

    # First run: everything is new, an artifact is published.
    first = run_report()
    assert first["artifact_written"] is True
    assert first["guides_rebuilt"] is True
    assert first["pages_seen"] == 4
    assert first["pages_denied"] == 1
    assert first["pages_processed"] == 3
    assert first["guides_index_drift"] == 0
    first_bytes = index_db.read_bytes()
    assert not list(artifact_dir.glob(".index.*.tmp"))

    # The artifact is redacted, complete and cites local pages (ROADMAP criteria 2 and 4).
    blob = first_bytes + (artifact_dir / "index.manifest.json").read_bytes()
    for secret in FORBIDDEN:
        assert (secret in blob) is False
    assert (b"[REDATTO]" in blob) is True
    with open_index(index_db) as reader:
        pages = reader.load_handbook()
        assert reader.meta.source_doc_id == SOURCE_ID
    assert [page.page_id for page in pages] == KEPT_IDS
    assert [page.position for page in pages] == [0, 1, 2]
    for page in pages:
        assert page.url == "handbook://" + page.page_id
        assert page.title
        assert page.revision_date_iso
    assert pages[1].revision_date_iso is not None
    assert pages[1].revision_date_iso.startswith("2026-09-20")

    code, out = run("search", "chunking", "--artifact-dir", str(artifact_dir))
    assert code == 0
    assert "AI-Engineering/DEMO_GUIDE.md:" in out
    assert out.rstrip().endswith("#t=30")

    # Unchanged inputs: nothing is processed and no file is touched (D-09, D-10, D-24).
    second = run_report()
    assert second["pages_processed"] == 0
    assert second["guides_rebuilt"] is False
    assert second["artifact_written"] is False
    assert second["content_hash"] == first["content_hash"]
    assert index_db.read_bytes() == first_bytes

    # Only a file's modification time changes: still nothing to do (SYNC-02).
    touched = handbook / "01-benvenuto.md"
    later = touched.stat().st_mtime + 3600
    os.utime(touched, (later, later))
    stamp_only = run_report()
    assert stamp_only["pages_processed"] == 0
    assert stamp_only["artifact_written"] is False
    assert index_db.read_bytes() == first_bytes

    # One page is edited: exactly that page is reprocessed and a new artifact is written.
    edited = handbook / "03-accesso-ufficio.md"
    with edited.open("a", encoding="utf-8") as handle:
        handle.write("\nAggiornamento sintetico.\n")
    third = run_report()
    assert third["pages_processed"] == 1
    assert third["artifact_written"] is True
    assert third["build_id"] is not None
    published = index_db.read_bytes()
    assert published != first_bytes

    # A failing build leaves the last artifact in place and no staged file behind.
    def partial_build(*_args: object, **_kwargs: object) -> None:
        dest = _args[1]
        assert isinstance(dest, Path)
        dest.write_bytes(b"partial")
        raise OSError("simulated disk failure")

    with edited.open("a", encoding="utf-8") as handle:
        handle.write("\nSecondo aggiornamento.\n")
    with monkeypatch.context() as patch:
        patch.setattr("buddy_sync.pipeline.build_index", partial_build)
        code, _out = run("run")
    assert code == 1
    assert index_db.read_bytes() == published
    assert not list(artifact_dir.glob(".index.*.tmp"))

    # The same inputs succeed once the failure is gone: a failed run is simply re-run.
    recovered = run_report()
    assert recovered["artifact_written"] is True
    assert index_db.read_bytes() != published

    joined = "".join(seen_output) + caplog.text
    for secret in (b"Wf9-synthetic-wifi-value", b"Zq9-synthetic-not-real"):
        assert (secret.decode() in joined) is False
