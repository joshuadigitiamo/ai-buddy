"""GcsArtifactStore over a FakeBucket: pointer-last publish, integrity, interruption, tracer."""

import asyncio
import hashlib
import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from fastmcp import Client
from tests.unit.buddy_core.conftest import FakeBucket, FakeBucketError
from tests.unit.mcp_server.conftest import NOW as SERVER_NOW
from tests.unit.mcp_server.conftest import WEB_BASE, make_content

from buddy_core.index_writer import build_index
from buddy_core.models import IndexContent
from buddy_core.store import (
    MANIFEST_NAME,
    ArtifactIntegrityError,
    ArtifactStore,
    GcsArtifactStore,
    LocalDirArtifactStore,
    check_bucket_name,
    check_object_prefix,
)
from buddy_mcp.config import McpSettings
from buddy_mcp.gaplog import InMemoryGapLog
from buddy_mcp.server import build_server
from buddy_mcp.snapshot import (
    SnapshotError,
    artifact_store_from_settings,
    load_snapshot,
    resolve_index_path,
)

NOW = datetime(2026, 11, 3, 10, 0, 0, tzinfo=UTC)
LATER = NOW + timedelta(hours=1)
PREFIX = "index/"
POINTER = PREFIX + MANIFEST_NAME


def _store(bucket: FakeBucket, cache_dir: Path, prefix: str = PREFIX) -> GcsArtifactStore:
    return GcsArtifactStore(bucket, prefix, cache_dir)


def _publish(store: ArtifactStore, content: IndexContent, now: datetime = NOW) -> tuple[Path, str]:
    staged = store.staging_path()
    meta = build_index(content, staged, now=now)
    return store.publish(staged, meta), meta.build_id


def _pointer(bucket: FakeBucket) -> dict[str, Any]:
    parsed: dict[str, Any] = json.loads(bucket.objects[POINTER])
    return parsed


def _write_pointer(bucket: FakeBucket, pointer: dict[str, Any]) -> None:
    bucket.objects[POINTER] = json.dumps(pointer).encode("utf-8")


def _files(directory: Path) -> list[str]:
    return sorted(p.name for p in directory.rglob("*"))


# --- publish ------------------------------------------------------------------------------------


def test_publish_uploads_the_db_object_then_the_pointer(
    sample_content: IndexContent, tmp_path: Path
) -> None:
    bucket = FakeBucket()
    _path, build_id = _publish(_store(bucket, tmp_path / "cache"), sample_content)

    assert bucket.uploads == [f"{PREFIX}index-{build_id}.db", POINTER]
    assert bucket.metadata[f"{PREFIX}index-{build_id}.db"]["content_type"] == (
        "application/vnd.sqlite3"
    )
    assert bucket.metadata[POINTER]["content_type"] == "application/json"


def test_pointer_carries_the_phase_one_keys_plus_the_object_name(
    sample_content: IndexContent, tmp_path: Path
) -> None:
    bucket = FakeBucket()
    path, build_id = _publish(_store(bucket, tmp_path / "cache"), sample_content)

    pointer = _pointer(bucket)
    assert set(pointer) == {
        "schema_version",
        "build_id",
        "content_hash",
        "created_at_utc",
        "sha256",
        "size_bytes",
        "object",
    }
    assert pointer["object"] == f"index-{build_id}.db"
    assert pointer["build_id"] == build_id
    assert pointer["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert pointer["size_bytes"] == path.stat().st_size


def test_publish_leaves_only_the_cached_index_in_the_cache_dir(
    sample_content: IndexContent, tmp_path: Path
) -> None:
    cache = tmp_path / "cache"
    _path, build_id = _publish(_store(FakeBucket(), cache), sample_content)
    assert _files(cache) == [f"index-{build_id}.db"]


def test_discard_removes_the_staged_file(tmp_path: Path) -> None:
    store = _store(FakeBucket(), tmp_path / "cache")
    staged = store.staging_path()
    staged.write_bytes(b"partial")
    store.discard(staged)
    store.discard(staged)
    assert not staged.exists()


def test_staging_path_creates_the_cache_dir_and_clears_stale_files(tmp_path: Path) -> None:
    cache = tmp_path / "deep" / "cache"
    store = _store(FakeBucket(), cache)
    first = store.staging_path()
    assert cache.is_dir()
    first.write_bytes(b"stale")
    second = store.staging_path()
    assert not first.exists()
    assert second != first


# --- read ---------------------------------------------------------------------------------------


def test_fresh_reader_downloads_and_verifies_the_published_index(
    sample_content: IndexContent, tmp_path: Path
) -> None:
    bucket = FakeBucket()
    _publish(_store(bucket, tmp_path / "writer"), sample_content)

    path = _store(bucket, tmp_path / "reader").latest_path()

    assert path is not None
    assert path.parent == tmp_path / "reader"
    assert hashlib.sha256(path.read_bytes()).hexdigest() == _pointer(bucket)["sha256"]
    assert _files(tmp_path / "reader") == [path.name]


def test_a_cached_index_is_reused_without_a_second_download(
    sample_content: IndexContent, tmp_path: Path
) -> None:
    bucket = FakeBucket()
    _publish(_store(bucket, tmp_path / "writer"), sample_content)
    reader = _store(bucket, tmp_path / "reader")

    first = reader.latest_path()
    second = reader.latest_path()

    assert first == second
    assert len(bucket.downloads) == 1


def test_a_damaged_cache_file_is_downloaded_again(
    sample_content: IndexContent, tmp_path: Path
) -> None:
    bucket = FakeBucket()
    _publish(_store(bucket, tmp_path / "writer"), sample_content)
    reader = _store(bucket, tmp_path / "reader")
    path = reader.latest_path()
    assert path is not None
    good = path.read_bytes()
    path.write_bytes(b"damaged")

    again = reader.latest_path()

    assert again == path
    assert path.read_bytes() == good
    assert len(bucket.downloads) == 2


def test_missing_pointer_means_no_published_index(tmp_path: Path) -> None:
    cache = tmp_path / "cache"
    assert _store(FakeBucket(), cache).latest_path() is None
    assert not list(cache.glob("*.db")) if cache.exists() else True


def test_the_reader_follows_the_newest_pointer(
    sample_content: IndexContent, tmp_path: Path
) -> None:
    bucket = FakeBucket()
    writer = _store(bucket, tmp_path / "writer")
    _publish(writer, sample_content, NOW)
    _path, second_id = _publish(writer, sample_content, LATER)

    reader_path = _store(bucket, tmp_path / "reader").latest_path()

    assert reader_path is not None
    assert reader_path.name == f"index-{second_id}.db"


# --- interruption (edge INFRA-04/concurrency) ---------------------------------------------------


def test_interrupted_db_upload_keeps_readers_on_the_previous_build(
    sample_content: IndexContent, tmp_path: Path
) -> None:
    bucket = FakeBucket()
    writer = _store(bucket, tmp_path / "writer")
    _path, first_id = _publish(writer, sample_content, NOW)
    pointer_before = bucket.objects[POINTER]

    bucket.fail_next_upload = True
    staged = writer.staging_path()
    meta = build_index(sample_content, staged, now=LATER)
    with pytest.raises(FakeBucketError):
        writer.publish(staged, meta)

    assert bucket.objects[POINTER] == pointer_before
    reader_path = _store(bucket, tmp_path / "reader").latest_path()
    assert reader_path is not None
    assert reader_path.name == f"index-{first_id}.db"


def test_interrupted_pointer_write_keeps_readers_on_the_previous_build(
    sample_content: IndexContent, tmp_path: Path
) -> None:
    bucket = FakeBucket()
    writer = _store(bucket, tmp_path / "writer")
    _path, first_id = _publish(writer, sample_content, NOW)
    pointer_before = bucket.objects[POINTER]

    bucket.fail_uploads_matching = MANIFEST_NAME
    staged = writer.staging_path()
    meta = build_index(sample_content, staged, now=LATER)
    with pytest.raises(FakeBucketError):
        writer.publish(staged, meta)

    # The new db object is orphaned, never referenced: a reader still resolves the old build.
    assert f"{PREFIX}index-{meta.build_id}.db" in bucket.objects
    assert bucket.objects[POINTER] == pointer_before
    reader_path = _store(bucket, tmp_path / "reader").latest_path()
    assert reader_path is not None
    assert reader_path.name == f"index-{first_id}.db"


def test_pointer_naming_a_missing_object_is_refused_not_half_served(
    sample_content: IndexContent, tmp_path: Path
) -> None:
    bucket = FakeBucket()
    _publish(_store(bucket, tmp_path / "writer"), sample_content)
    del bucket.objects[f"{PREFIX}{_pointer(bucket)['object']}"]

    with pytest.raises(ArtifactIntegrityError, match="missing"):
        _store(bucket, tmp_path / "reader").latest_path()
    assert not list((tmp_path / "reader").glob("*"))


def test_upload_that_the_bucket_stored_differently_never_gets_a_pointer(
    sample_content: IndexContent, tmp_path: Path
) -> None:
    bucket = FakeBucket()
    bucket.corrupt_uploads_matching = ".db"
    writer = _store(bucket, tmp_path / "writer")
    staged = writer.staging_path()
    meta = build_index(sample_content, staged, now=NOW)

    with pytest.raises(ArtifactIntegrityError, match="checksum"):
        writer.publish(staged, meta)

    assert POINTER not in bucket.objects


# --- integrity ----------------------------------------------------------------------------------


def test_pointer_sha256_that_does_not_match_is_a_checksum_mismatch(
    sample_content: IndexContent, tmp_path: Path
) -> None:
    bucket = FakeBucket()
    _publish(_store(bucket, tmp_path / "writer"), sample_content)
    _write_pointer(bucket, {**_pointer(bucket), "sha256": "0" * 64})

    with pytest.raises(ArtifactIntegrityError, match="index checksum mismatch"):
        _store(bucket, tmp_path / "reader").latest_path()
    assert _files(tmp_path / "reader") == []


def test_pointer_size_that_does_not_match_is_a_checksum_mismatch(
    sample_content: IndexContent, tmp_path: Path
) -> None:
    bucket = FakeBucket()
    _publish(_store(bucket, tmp_path / "writer"), sample_content)
    pointer = _pointer(bucket)
    _write_pointer(bucket, {**pointer, "size_bytes": pointer["size_bytes"] + 1})

    with pytest.raises(ArtifactIntegrityError, match="index checksum mismatch"):
        _store(bucket, tmp_path / "reader").latest_path()
    assert _files(tmp_path / "reader") == []


@pytest.mark.parametrize("object_name", ["../x.db", "other.db", "/abs/index-x.db", "", None])
def test_pointer_object_name_other_than_the_build_object_is_refused(
    sample_content: IndexContent, tmp_path: Path, object_name: str | None
) -> None:
    bucket = FakeBucket()
    _publish(_store(bucket, tmp_path / "writer"), sample_content)
    bucket.objects["x.db"] = b"outside"
    bucket.objects["other.db"] = b"outside"
    _write_pointer(bucket, {**_pointer(bucket), "object": object_name})
    reader_dir = tmp_path / "reader"

    with pytest.raises(ArtifactIntegrityError):
        _store(bucket, reader_dir).latest_path()

    assert bucket.downloads == []
    # Nothing was written outside the writer's own cache: no reader cache, no stray file.
    assert sorted(p.name for p in tmp_path.iterdir()) == ["writer"]


@pytest.mark.parametrize("build_id", ["../evil", "a/b", "", "x" * 200, "a b"])
def test_pointer_build_id_that_is_not_a_safe_name_is_refused(
    sample_content: IndexContent, tmp_path: Path, build_id: str
) -> None:
    bucket = FakeBucket()
    _publish(_store(bucket, tmp_path / "writer"), sample_content)
    _write_pointer(
        bucket, {**_pointer(bucket), "build_id": build_id, "object": f"index-{build_id}.db"}
    )
    with pytest.raises(ArtifactIntegrityError):
        _store(bucket, tmp_path / "reader").latest_path()


@pytest.mark.parametrize(
    "raw",
    [b"not json", b"[]", b'"text"', b"{}", b"\xff\xfe"],
)
def test_unreadable_pointer_is_refused(tmp_path: Path, raw: bytes) -> None:
    bucket = FakeBucket()
    bucket.objects[POINTER] = raw
    with pytest.raises(ArtifactIntegrityError, match="pointer"):
        _store(bucket, tmp_path / "reader").latest_path()


@pytest.mark.parametrize(
    "field,value",
    [
        ("sha256", "short"),
        ("sha256", 7),
        ("size_bytes", "9"),
        ("size_bytes", True),
        ("size_bytes", -1),
    ],
)
def test_pointer_fields_of_the_wrong_shape_are_refused(
    sample_content: IndexContent, tmp_path: Path, field: str, value: object
) -> None:
    bucket = FakeBucket()
    _publish(_store(bucket, tmp_path / "writer"), sample_content)
    _write_pointer(bucket, {**_pointer(bucket), field: value})
    with pytest.raises(ArtifactIntegrityError, match="pointer"):
        _store(bucket, tmp_path / "reader").latest_path()


def test_publish_refuses_a_build_id_that_is_not_a_safe_object_name(
    sample_content: IndexContent, tmp_path: Path
) -> None:
    bucket = FakeBucket()
    store = _store(bucket, tmp_path / "cache")
    staged = store.staging_path()
    meta = build_index(sample_content, staged, now=NOW)
    unsafe = replace(meta, build_id="../evil")
    with pytest.raises(ArtifactIntegrityError):
        store.publish(staged, unsafe)
    assert bucket.uploads == []


# --- name validators ----------------------------------------------------------------------------


@pytest.mark.parametrize("name", ["abc", "my-bucket", "my_bucket.v2", "a" * 63, "0a0"])
def test_check_bucket_name_accepts_gcs_names(name: str) -> None:
    assert check_bucket_name(name) == name


@pytest.mark.parametrize(
    "name",
    ["", "ab", "a" * 64, "Upper", "-abc", "abc-", "a b c", "a/b", "gs://abc", "ab..", "é-bucket"],
)
def test_check_bucket_name_refuses_the_rest_without_echoing(name: str) -> None:
    with pytest.raises(ValueError) as caught:
        check_bucket_name(name)
    with pytest.raises(ValueError) as reference:
        check_bucket_name("NOT_A_BUCKET")
    # One fixed message for every input: nothing of the value can be in it.
    assert str(caught.value) == str(reference.value)


@pytest.mark.parametrize("prefix", ["", "index/", "a/b/", "v1.0/data_x/", "a-b/"])
def test_check_object_prefix_accepts_empty_and_slash_terminated_segments(prefix: str) -> None:
    assert check_object_prefix(prefix) == prefix


@pytest.mark.parametrize(
    "prefix", ["../", "/a/", "A/", "a", "a//b/", "a/../b/", "./", "a b/", "index/ ", "..", "a/b"]
)
def test_check_object_prefix_refuses_the_rest_without_echoing(prefix: str) -> None:
    with pytest.raises(ValueError) as caught:
        check_object_prefix(prefix)
    with pytest.raises(ValueError) as reference:
        check_object_prefix("NOT/A/PREFIX")
    # One fixed message for every input: nothing of the value can be in it.
    assert str(caught.value) == str(reference.value)


# --- store factory and the cold-start tracer ----------------------------------------------------


def _gcs_settings(cache: Path, **overrides: Any) -> McpSettings:
    values: dict[str, Any] = {
        "artifact_store": "gcs",
        "artifact_bucket": "bucket-x",
        "artifact_prefix": PREFIX,
        "artifact_dir": cache,
        "guides_web_base": WEB_BASE,
        "auth_mode": "off",
        "deploy_env": "local",
    }
    values.update(overrides)
    return McpSettings(**values)


def _never_a_bucket(name: str) -> FakeBucket:
    raise AssertionError("the local store must not build a bucket")


def test_gcs_settings_select_a_gcs_store_over_the_named_bucket(tmp_path: Path) -> None:
    bucket = FakeBucket()
    names: list[str] = []

    def factory(name: str) -> FakeBucket:
        names.append(name)
        return bucket

    store = artifact_store_from_settings(_gcs_settings(tmp_path / "cache"), bucket_factory=factory)

    assert isinstance(store, GcsArtifactStore)
    assert names == ["bucket-x"]


def test_gcs_without_a_cache_dir_uses_the_default_cache(tmp_path: Path) -> None:
    store = artifact_store_from_settings(
        _gcs_settings(tmp_path, artifact_dir=None), bucket_factory=lambda _n: FakeBucket()
    )
    assert isinstance(store, GcsArtifactStore)


def test_local_settings_keep_the_local_directory_store(
    sample_content: IndexContent, tmp_path: Path
) -> None:
    directory = tmp_path / "artifacts"
    _publish(LocalDirArtifactStore(directory), sample_content)
    settings = McpSettings(
        artifact_dir=directory, guides_web_base=WEB_BASE, auth_mode="off", deploy_env="local"
    )

    store = artifact_store_from_settings(settings, bucket_factory=_never_a_bucket)

    assert isinstance(store, LocalDirArtifactStore)
    assert resolve_index_path(store) == directory / "index.db"


def test_local_store_keeps_both_existing_error_messages(tmp_path: Path) -> None:
    missing = tmp_path / "nope"
    settings = McpSettings(
        artifact_dir=missing, guides_web_base=WEB_BASE, auth_mode="off", deploy_env="local"
    )
    with pytest.raises(SnapshotError, match="artifact directory does not exist"):
        artifact_store_from_settings(settings, bucket_factory=_never_a_bucket)
    assert not missing.exists()

    empty = tmp_path / "empty"
    empty.mkdir()
    local = McpSettings(
        artifact_dir=empty, guides_web_base=WEB_BASE, auth_mode="off", deploy_env="local"
    )
    store = artifact_store_from_settings(local, bucket_factory=_never_a_bucket)
    with pytest.raises(SnapshotError, match="no index.db in artifact directory"):
        resolve_index_path(store)


def test_gcs_missing_pointer_names_the_store_not_the_bucket(tmp_path: Path) -> None:
    store = artifact_store_from_settings(
        _gcs_settings(tmp_path / "cache"), bucket_factory=lambda _n: FakeBucket()
    )
    with pytest.raises(SnapshotError) as caught:
        resolve_index_path(store)
    assert "artifact store" in str(caught.value)
    assert "bucket-x" not in str(caught.value)


def test_gcs_store_serves_a_cited_handbook_tool_answer(tmp_path: Path) -> None:
    bucket = FakeBucket()
    _publish(_store(bucket, tmp_path / "publisher"), make_content(), SERVER_NOW)
    settings = _gcs_settings(tmp_path / "server-cache")
    store = artifact_store_from_settings(settings, bucket_factory=lambda _name: bucket)

    snapshot = load_snapshot(resolve_index_path(store))
    try:
        server = build_server(
            settings, snapshot=snapshot, gaplog=InMemoryGapLog(), now=lambda: SERVER_NOW
        )

        async def call() -> dict[str, Any]:
            async with Client(server) as client:
                result = await client.call_tool("handbook_search", {"query": "ferie"})
            assert result.structured_content is not None
            return dict(result.structured_content)

        out = asyncio.run(call())
    finally:
        snapshot.reader.close()
        snapshot.handbook_index.close()

    assert out["status"] == "ok"
    assert out["results"][0]["source_url"] == "handbook://02-ferie"
    cached = [p.name for p in (tmp_path / "server-cache").glob("index-*.db")]
    assert cached == [f"index-{snapshot.meta.build_id}.db"]
