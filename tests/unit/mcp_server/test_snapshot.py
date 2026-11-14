"""Cold-start snapshot: fail fast, read-only, no side effects on the artifact directory."""

import json
import shutil
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from tests.unit.buddy_core.conftest import FakeBucket
from tests.unit.mcp_server.conftest import (
    MAPPED,
    WEB_BASE,
    make_content,
    make_page,
    write_index,
)

from buddy_core.index_reader import IndexVersionError
from buddy_core.index_writer import build_index
from buddy_core.store import MANIFEST_NAME, ArtifactStore, BucketPort, GcsArtifactStore
from buddy_mcp.config import McpSettings
from buddy_mcp.snapshot import (
    SnapshotError,
    artifact_store_from_settings,
    load_snapshot,
    resolve_index_path,
)


def _names(directory: Path) -> list[str]:
    return sorted(p.name for p in directory.iterdir())


def _no_bucket(name: str) -> BucketPort:
    raise AssertionError("a local store must not build a bucket")


def _local_store(directory: Path) -> ArtifactStore:
    settings = McpSettings(
        artifact_dir=directory, guides_web_base=WEB_BASE, auth_mode="off", deploy_env="local"
    )
    return artifact_store_from_settings(settings, bucket_factory=_no_bucket)


def test_missing_directory_fails_and_is_not_created(tmp_path: Path) -> None:
    missing = tmp_path / "nope"
    with pytest.raises(SnapshotError, match="artifact directory does not exist"):
        _local_store(missing)
    assert not missing.exists()


def test_empty_directory_has_no_index(tmp_path: Path) -> None:
    with pytest.raises(SnapshotError, match="no index.db"):
        resolve_index_path(_local_store(tmp_path))
    assert _names(tmp_path) == []


def test_resolve_finds_the_published_index(index_dir: Path) -> None:
    assert resolve_index_path(_local_store(index_dir)) == index_dir / "index.db"


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
    loaded = load_snapshot(resolve_index_path(_local_store(index_dir)))
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


# --- bucket store: what the server refuses to serve (T-04-12, T-04-13) -------------------------

_POINTER = "idx/" + MANIFEST_NAME


def _published_bucket(tmp_path: Path) -> FakeBucket:
    bucket = FakeBucket()
    writer = GcsArtifactStore(bucket, "idx/", tmp_path / "writer")
    staged = writer.staging_path()
    meta = build_index(make_content(), staged, now=datetime(2026, 11, 3, 10, tzinfo=UTC))
    writer.publish(staged, meta)
    return bucket


def _gcs_store(bucket: FakeBucket, cache: Path) -> ArtifactStore:
    settings = McpSettings(
        artifact_store="gcs",
        artifact_bucket="bucket-x",
        artifact_prefix="idx/",
        artifact_dir=cache,
        guides_web_base=WEB_BASE,
        auth_mode="off",
        deploy_env="local",
    )
    return artifact_store_from_settings(settings, bucket_factory=lambda _name: bucket)


def _tamper(bucket: FakeBucket, **changes: Any) -> None:
    pointer = json.loads(bucket.objects[_POINTER])
    bucket.objects[_POINTER] = json.dumps({**pointer, **changes}).encode("utf-8")


def test_gcs_published_index_loads_into_a_snapshot(tmp_path: Path) -> None:
    bucket = _published_bucket(tmp_path)
    loaded = load_snapshot(resolve_index_path(_gcs_store(bucket, tmp_path / "cache")))
    try:
        assert list(loaded.pages)[0] == "01-benvenuto"
    finally:
        loaded.reader.close()
        loaded.handbook_index.close()


def test_gcs_pointer_with_another_sha256_is_a_checksum_mismatch(tmp_path: Path) -> None:
    bucket = _published_bucket(tmp_path)
    _tamper(bucket, sha256="0" * 64)
    with pytest.raises(SnapshotError, match="index checksum mismatch"):
        resolve_index_path(_gcs_store(bucket, tmp_path / "cache"))
    assert not list((tmp_path / "cache").glob("index-*.db"))


def test_gcs_pointer_with_another_size_is_a_checksum_mismatch(tmp_path: Path) -> None:
    bucket = _published_bucket(tmp_path)
    pointer = json.loads(bucket.objects[_POINTER])
    _tamper(bucket, size_bytes=pointer["size_bytes"] + 1)
    with pytest.raises(SnapshotError, match="index checksum mismatch"):
        resolve_index_path(_gcs_store(bucket, tmp_path / "cache"))


@pytest.mark.parametrize("object_name", ["../x.db", "other.db"])
def test_gcs_pointer_object_name_outside_the_build_object_is_refused(
    tmp_path: Path, object_name: str
) -> None:
    bucket = _published_bucket(tmp_path)
    _tamper(bucket, object=object_name)
    cache = tmp_path / "cache"
    with pytest.raises(SnapshotError, match="unexpected object"):
        resolve_index_path(_gcs_store(bucket, cache))
    assert sorted(p.name for p in tmp_path.iterdir()) == ["writer"]


def test_gcs_pointer_naming_a_missing_object_is_refused(tmp_path: Path) -> None:
    bucket = _published_bucket(tmp_path)
    pointer = json.loads(bucket.objects[_POINTER])
    del bucket.objects["idx/" + pointer["object"]]
    with pytest.raises(SnapshotError, match="missing"):
        resolve_index_path(_gcs_store(bucket, tmp_path / "cache"))
