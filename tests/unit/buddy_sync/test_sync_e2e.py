"""End to end on fixtures: ``main(["run"])`` publishes a searchable, redacted artifact."""

import json
import logging
import shutil
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

import httpx
import pytest

from buddy_core.index_reader import open_index
from buddy_sync.chunker import heading_outline
from buddy_sync.cli import main
from buddy_sync.guides import select_guide_files
from buddy_sync.guides_index import write_guides_index

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"
TOKEN = "tok-synthetic-Kd8-not-a-real-token"
DOC_URL_PREFIX = "https://app.clickup.com/123/v/dc/demo-doc/"
SECRETS = (b"demo-page-wifi", b"Wf9-synthetic-wifi-value", b"Zq9-synthetic-not-real")

Payload = list[dict[str, Any]]
RepoFactory = Callable[[Mapping[str, str] | Path], Path]


def _walk(pages: Payload) -> list[dict[str, Any]]:
    flat: list[dict[str, Any]] = []
    for page in pages:
        flat.append(page)
        flat.extend(_walk(page["pages"]))
    return flat


def _page(pages: Payload, page_id: str) -> dict[str, Any]:
    return next(page for page in _walk(pages) if page["id"] == page_id)


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
    artifact_dir = tmp_path / "artifacts"
    for name, value in {
        "CLICKUP_TOKEN": TOKEN,
        "CLICKUP_WORKSPACE_ID": "123",
        "CLICKUP_DOC_ID": "demo-doc",
        "REDACT_PAGE_IDS": "demo-page-wifi",
        "GUIDES_REPO_URL": str(repo),
        "GUIDES_BRANCH": "master",
        "GUIDES_CHECKOUT_DIR": str(tmp_path / "checkout"),
        "ARTIFACT_DIR": str(artifact_dir),
    }.items():
        monkeypatch.setenv(name, value)
    monkeypatch.delenv("GUIDES_REPO_TOKEN", raising=False)

    payload: Payload = json.loads((FIXTURES / "clickup" / "pages.json").read_text("utf-8"))

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v3/workspaces/123/docs/demo-doc/pages"
        return httpx.Response(200, json=payload)

    transport = httpx.MockTransport(handler)
    seen_output: list[str] = []

    def run(*argv: str) -> tuple[int, str]:
        code = main(list(argv), transport=transport)
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
    assert first["pages_denied"] == 1
    assert first["guides_index_drift"] == 0
    first_bytes = index_db.read_bytes()
    assert not list(artifact_dir.glob(".index.*.tmp"))

    # The artifact is redacted and complete (ROADMAP criteria 2 and 4).
    for secret in SECRETS:
        assert secret not in first_bytes
    with open_index(index_db) as reader:
        pages = reader.load_handbook()
    assert pages
    assert "demo-page-wifi" not in {page.page_id for page in pages}
    for page in pages:
        assert page.url.startswith(DOC_URL_PREFIX)
        assert page.title
        assert page.revision_date_iso

    code, out = run("search", "chunking", "--artifact-dir", str(artifact_dir))
    assert code == 0
    assert "AI-Engineering/DEMO_GUIDE.md:" in out
    assert "#t=30" in out

    # Unchanged inputs: nothing is processed and no file is touched (D-09, D-10, D-24).
    second = run_report()
    assert second["pages_processed"] == 0
    assert second["guides_rebuilt"] is False
    assert second["artifact_written"] is False
    assert second["content_hash"] == first["content_hash"]
    assert index_db.read_bytes() == first_bytes

    # Only ClickUp's update timestamp changes: still nothing to do (SYNC-02).
    for raw in _walk(payload):
        raw["date_updated"] += 1
    stamp_only = run_report()
    assert stamp_only["pages_processed"] == 0
    assert stamp_only["artifact_written"] is False
    assert index_db.read_bytes() == first_bytes

    # One page is edited: exactly that page is reprocessed and a new artifact is written.
    edited = _page(payload, "demo-page-0002")
    edited["date_edited"] += 5000
    edited["content"] += "\n\nAggiornamento sintetico."
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

    edited["date_edited"] += 5000
    edited["content"] += "\n\nSecondo aggiornamento."
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

    assert TOKEN not in "".join(seen_output)
    assert TOKEN not in caplog.text
