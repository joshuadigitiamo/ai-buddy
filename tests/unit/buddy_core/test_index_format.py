"""Format contract: versioning, logical content hash, build id, validation, single file."""

import re
import sqlite3
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from buddy_core.index_reader import IndexFormatError, IndexVersionError, open_index
from buddy_core.index_writer import build_index, compute_content_hash
from buddy_core.models import IndexContent, VideoLink
from buddy_core.schema import META_KEYS, SCHEMA_MAJOR

T0 = datetime(2026, 11, 3, 10, 0, 0, tzinfo=UTC)


def _build(content: IndexContent, tmp_path: Path, name: str, now: datetime = T0) -> Path:
    dest = tmp_path / name
    build_index(content, dest, now=now)
    return dest


def _sql(path: Path, statement: str) -> None:
    conn = sqlite3.connect(path)
    try:
        conn.execute(statement)
        conn.commit()
    finally:
        conn.close()


def test_user_version_and_meta_keys_present(sample_content: IndexContent, tmp_path: Path) -> None:
    path = _build(sample_content, tmp_path, "a.db")
    conn = sqlite3.connect(path)
    try:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_MAJOR == 1
        keys = {row[0] for row in conn.execute("SELECT key FROM meta")}
    finally:
        conn.close()
    assert keys == set(META_KEYS)


def test_user_version_mismatch_is_refused(sample_content: IndexContent, tmp_path: Path) -> None:
    path = _build(sample_content, tmp_path, "a.db")
    _sql(path, "PRAGMA user_version = 2")
    with pytest.raises(IndexVersionError):
        open_index(path)


def test_schema_version_major_mismatch_is_refused(
    sample_content: IndexContent, tmp_path: Path
) -> None:
    path = _build(sample_content, tmp_path, "a.db")
    _sql(path, "UPDATE meta SET value = '2.0.0' WHERE key = 'schema_version'")
    with pytest.raises(IndexVersionError):
        open_index(path)


def test_missing_meta_key_is_a_format_error(sample_content: IndexContent, tmp_path: Path) -> None:
    path = _build(sample_content, tmp_path, "a.db")
    _sql(path, "DELETE FROM meta WHERE key = 'guides_commit_sha'")
    with pytest.raises(IndexFormatError) as info:
        open_index(path)
    assert not isinstance(info.value, IndexVersionError)


def test_missing_file_raises_file_not_found(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        open_index(tmp_path / "nope.db")


def test_same_content_at_two_times_same_hash_different_build_id(
    sample_content: IndexContent, tmp_path: Path
) -> None:
    first = build_index(sample_content, tmp_path / "a.db", now=T0)
    second = build_index(sample_content, tmp_path / "b.db", now=T0 + timedelta(hours=5))
    assert first.content_hash == second.content_hash
    assert first.build_id != second.build_id
    assert first.created_at_utc != second.created_at_utc


def test_hash_is_independent_of_row_order(sample_content: IndexContent) -> None:
    reordered = replace(
        sample_content,
        handbook=tuple(reversed(sample_content.handbook)),
        chunks=tuple(reversed(sample_content.chunks)),
    )
    assert compute_content_hash(reordered) == compute_content_hash(sample_content)


def test_changing_a_page_changes_the_hash(sample_content: IndexContent) -> None:
    changed = replace(
        sample_content,
        handbook=(
            replace(sample_content.handbook[0], content_md="Different body."),
            sample_content.handbook[1],
        ),
    )
    assert compute_content_hash(changed) != compute_content_hash(sample_content)


def test_changing_a_video_offset_changes_the_hash(sample_content: IndexContent) -> None:
    key = next(iter(sample_content.videos))
    changed = replace(
        sample_content,
        videos={key: VideoLink("https://v.example.invalid/x.mp4", 1, 99.0, "scene")},
    )
    assert compute_content_hash(changed) != compute_content_hash(sample_content)


def test_build_id_format_is_timestamp_plus_hash_prefix(
    sample_content: IndexContent, tmp_path: Path
) -> None:
    meta = build_index(sample_content, tmp_path / "a.db", now=T0)
    assert re.fullmatch(r"\d{8}T\d{6}Z-[0-9a-f]{12}", meta.build_id)
    assert meta.build_id == f"20261103T100000Z-{meta.content_hash[:12]}"


def test_video_key_without_chunk_is_rejected(sample_content: IndexContent, tmp_path: Path) -> None:
    bad = replace(
        sample_content,
        videos={"no/such#chunk": VideoLink("https://v.example.invalid/x.mp4", 1, None, "scene")},
    )
    with pytest.raises(ValueError):
        build_index(bad, tmp_path / "a.db", now=T0)


def test_repeated_handbook_positions_are_rejected(
    sample_content: IndexContent, tmp_path: Path
) -> None:
    page = sample_content.handbook[0]
    bad = replace(sample_content, handbook=(page, replace(page, page_id="p-dup")))
    with pytest.raises(ValueError):
        build_index(bad, tmp_path / "a.db", now=T0)


def test_existing_destination_is_refused(sample_content: IndexContent, tmp_path: Path) -> None:
    path = _build(sample_content, tmp_path, "a.db")
    with pytest.raises(FileExistsError):
        build_index(sample_content, path, now=T0)


def test_artifact_is_a_single_file_without_sidecars(
    sample_content: IndexContent, tmp_path: Path
) -> None:
    path = _build(sample_content, tmp_path, "index.db")
    with open_index(path) as reader:
        reader.search_guides("chunking")
        reader.load_handbook()
    names = {p.name for p in tmp_path.iterdir()}
    assert names == {"index.db"}


def test_journal_mode_is_delete(sample_content: IndexContent, tmp_path: Path) -> None:
    path = _build(sample_content, tmp_path, "a.db")
    conn = sqlite3.connect(path)
    try:
        assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "delete"
    finally:
        conn.close()


def test_no_date_updated_column_exists(sample_content: IndexContent, tmp_path: Path) -> None:
    path = _build(sample_content, tmp_path, "a.db")
    conn = sqlite3.connect(path)
    try:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(handbook_pages)")}
    finally:
        conn.close()
    assert "date_updated" not in columns
    assert {"date_edited_raw", "date_created_raw", "revision_date_iso"} <= columns
