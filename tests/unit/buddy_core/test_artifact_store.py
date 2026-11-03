"""ArtifactStore: atomic publish, manifest, failure keeps the previous artifact, stale cleanup."""

import hashlib
import json
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest

from buddy_core.index_reader import open_index
from buddy_core.index_writer import build_index
from buddy_core.models import IndexContent
from buddy_core.store import INDEX_NAME, MANIFEST_NAME, ArtifactStore, LocalDirArtifactStore

NOW = datetime(2026, 11, 3, 10, 0, 0, tzinfo=UTC)


def _publish(store: ArtifactStore, content: IndexContent) -> Path:
    staged = store.staging_path()
    meta = build_index(content, staged, now=NOW)
    return store.publish(staged, meta)


def test_latest_path_is_none_on_empty_dir(tmp_path: Path) -> None:
    assert LocalDirArtifactStore(tmp_path / "new" / "dir").latest_path() is None


def test_publish_leaves_exactly_index_and_manifest(
    sample_content: IndexContent, tmp_path: Path
) -> None:
    store = LocalDirArtifactStore(tmp_path)
    _publish(store, sample_content)
    assert {p.name for p in tmp_path.iterdir()} == {INDEX_NAME, MANIFEST_NAME}


def test_manifest_describes_the_published_bytes(
    sample_content: IndexContent, tmp_path: Path
) -> None:
    store = LocalDirArtifactStore(tmp_path)
    final = _publish(store, sample_content)
    manifest = json.loads((tmp_path / MANIFEST_NAME).read_text(encoding="utf-8"))
    assert set(manifest) == {
        "schema_version",
        "build_id",
        "content_hash",
        "created_at_utc",
        "sha256",
        "size_bytes",
    }
    assert manifest["sha256"] == hashlib.sha256(final.read_bytes()).hexdigest()
    assert manifest["size_bytes"] == final.stat().st_size
    with open_index(final) as reader:
        assert manifest["build_id"] == reader.meta.build_id
        assert manifest["content_hash"] == reader.meta.content_hash


def test_failed_build_keeps_previous_artifact_byte_identical(
    sample_content: IndexContent, tmp_path: Path
) -> None:
    store = LocalDirArtifactStore(tmp_path)
    final = _publish(store, sample_content)
    before = final.read_bytes()
    manifest_before = (tmp_path / MANIFEST_NAME).read_bytes()

    page = sample_content.handbook[0]
    broken = replace(sample_content, handbook=(page, replace(page, page_id="p-dup")))
    staged = store.staging_path()
    with pytest.raises(ValueError):
        build_index(broken, staged, now=NOW)
    store.discard(staged)

    assert final.read_bytes() == before
    assert (tmp_path / MANIFEST_NAME).read_bytes() == manifest_before
    assert {p.name for p in tmp_path.iterdir()} == {INDEX_NAME, MANIFEST_NAME}


def test_interrupted_build_leftover_is_removed_by_next_staging_path(
    sample_content: IndexContent, tmp_path: Path
) -> None:
    store = LocalDirArtifactStore(tmp_path)
    final = _publish(store, sample_content)
    before = final.read_bytes()
    stale = tmp_path / ".index.deadbeef.tmp"
    stale.write_bytes(b"half written")

    staged = store.staging_path()

    assert not stale.exists()
    assert staged.parent == tmp_path
    assert final.read_bytes() == before


def test_discard_is_idempotent(tmp_path: Path) -> None:
    store = LocalDirArtifactStore(tmp_path)
    staged = store.staging_path()
    store.discard(staged)
    store.discard(staged)


def test_second_publish_replaces_atomically(sample_content: IndexContent, tmp_path: Path) -> None:
    store = LocalDirArtifactStore(tmp_path)
    _publish(store, sample_content)
    newer = replace(sample_content, guides_commit_sha="2" * 40)
    final = _publish(store, newer)
    with open_index(final) as reader:
        assert reader.meta.guides_commit_sha == "2" * 40
    assert {p.name for p in tmp_path.iterdir()} == {INDEX_NAME, MANIFEST_NAME}
