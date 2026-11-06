"""Cold-start snapshot: fail fast, read-only, no side effects on the artifact directory."""

import shutil
import sqlite3
from pathlib import Path

import pytest
from tests.unit.mcp_server.conftest import MAPPED, make_content, make_page, write_index

from buddy_core.index_reader import IndexVersionError
from buddy_mcp.snapshot import SnapshotError, load_snapshot, resolve_index_path


def _names(directory: Path) -> list[str]:
    return sorted(p.name for p in directory.iterdir())


def test_missing_directory_fails_and_is_not_created(tmp_path: Path) -> None:
    missing = tmp_path / "nope"
    with pytest.raises(SnapshotError):
        resolve_index_path(missing)
    assert not missing.exists()


def test_empty_directory_has_no_index(tmp_path: Path) -> None:
    with pytest.raises(SnapshotError, match="no index.db"):
        resolve_index_path(tmp_path)
    assert _names(tmp_path) == []


def test_resolve_finds_the_published_index(index_dir: Path) -> None:
    assert resolve_index_path(index_dir) == index_dir / "index.db"


def test_other_schema_major_is_refused(index_dir: Path, tmp_path: Path) -> None:
    broken = tmp_path / "other-major.db"
    shutil.copy(index_dir / "index.db", broken)
    conn = sqlite3.connect(broken)
    conn.execute("PRAGMA user_version = 99")
    conn.commit()
    conn.close()
    with pytest.raises(IndexVersionError):
        load_snapshot(broken)


def test_page_without_revision_date_names_the_page(tmp_path: Path) -> None:
    content = make_content(pages=(make_page("09-senza-data", 0, "T", "Corpo.", None),))
    path = write_index(tmp_path / "undated", content)
    with pytest.raises(SnapshotError, match="09-senza-data"):
        load_snapshot(path)


def test_loading_leaves_the_artifact_directory_untouched(index_dir: Path) -> None:
    before = _names(index_dir)
    loaded = load_snapshot(resolve_index_path(index_dir))
    loaded.reader.search_guides("chunking")
    loaded.reader.close()
    assert _names(index_dir) == before


def test_snapshot_holds_pages_chunks_and_videos(index_dir: Path) -> None:
    loaded = load_snapshot(index_dir / "index.db")
    try:
        assert list(loaded.pages)[0] == "01-benvenuto"
        assert MAPPED.chunk_key in loaded.chunks
        assert MAPPED.chunk_key in loaded.videos
        assert loaded.meta.guides_commit_sha == "1" * 40
    finally:
        loaded.reader.close()
