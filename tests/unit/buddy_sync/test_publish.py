"""publish_index and ``buddy_sync publish``: db object first, pointer last, idempotent, ids only."""

import json
import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from tests.unit.buddy_core.conftest import FakeBucket, SimulatedUploadError
from tests.unit.mcp_server.conftest import make_content

from buddy_core.gcs_bucket import BucketError
from buddy_core.index_writer import build_index
from buddy_core.models import IndexMeta
from buddy_core.store import (
    INDEX_NAME,
    MANIFEST_NAME,
    GcsArtifactStore,
    LocalDirArtifactStore,
)
from buddy_sync.cli import main
from buddy_sync.publish import PublishError, PublishResult, publish_index

NOW = datetime(2026, 11, 3, 10, 0, 0, tzinfo=UTC)
LATER = NOW + timedelta(hours=1)
PREFIX = "index/"
POINTER = PREFIX + MANIFEST_NAME
BUCKET_NAME = "demo-ai-buddy-index"


def _local_index(root: Path, *, now: datetime = NOW, pages: int | None = None) -> IndexMeta:
    """Write a real index.db and its manifest into ``root`` the way the sync does."""
    store = LocalDirArtifactStore(root)
    staged = store.staging_path()
    content = make_content()
    if pages is not None:
        content = make_content(pages=content.handbook[:pages])
    meta = build_index(content, staged, now=now)
    store.publish(staged, meta)
    return meta


def _store(bucket: FakeBucket, tmp_path: Path) -> GcsArtifactStore:
    return GcsArtifactStore(bucket, PREFIX, tmp_path / "cache")


def _db_object(meta: IndexMeta) -> str:
    return f"{PREFIX}index-{meta.build_id}.db"


def test_publish_uploads_the_db_object_then_the_pointer(tmp_path: Path) -> None:
    meta = _local_index(tmp_path / "artifacts")
    bucket = FakeBucket()
    result = publish_index(tmp_path / "artifacts", _store(bucket, tmp_path), bucket)
    assert result == PublishResult("published", meta.build_id)
    assert bucket.uploads == [_db_object(meta), POINTER]
    pointer = json.loads(bucket.objects[POINTER])
    assert pointer["build_id"] == meta.build_id
    assert pointer["content_hash"] == meta.content_hash
    assert pointer["object"] == f"index-{meta.build_id}.db"


def test_the_published_index_is_readable_by_a_second_store(tmp_path: Path) -> None:
    meta = _local_index(tmp_path / "artifacts")
    bucket = FakeBucket()
    publish_index(tmp_path / "artifacts", _store(bucket, tmp_path), bucket)
    reader = GcsArtifactStore(bucket, PREFIX, tmp_path / "reader-cache")
    path = reader.latest_path()
    assert path is not None
    assert path.read_bytes() == (tmp_path / "artifacts" / INDEX_NAME).read_bytes()
    assert path.name == f"index-{meta.build_id}.db"


def test_same_content_hash_in_the_pointer_uploads_nothing(tmp_path: Path) -> None:
    meta = _local_index(tmp_path / "artifacts")
    bucket = FakeBucket()
    publish_index(tmp_path / "artifacts", _store(bucket, tmp_path), bucket)
    uploads_before = list(bucket.uploads)
    again = publish_index(tmp_path / "artifacts", _store(bucket, tmp_path / "second"), bucket)
    assert again == PublishResult("unchanged", meta.build_id)
    assert bucket.uploads == uploads_before


def test_new_content_publishes_a_new_build_and_moves_the_pointer(tmp_path: Path) -> None:
    first = _local_index(tmp_path / "first")
    second = _local_index(tmp_path / "second", now=LATER, pages=1)
    assert first.content_hash != second.content_hash
    bucket = FakeBucket()
    publish_index(tmp_path / "first", _store(bucket, tmp_path), bucket)
    result = publish_index(tmp_path / "second", _store(bucket, tmp_path / "again"), bucket)
    assert result == PublishResult("published", second.build_id)
    assert json.loads(bucket.objects[POINTER])["build_id"] == second.build_id
    # The previous build stays in the bucket, so a rollback only rewrites the pointer.
    assert _db_object(first) in bucket.objects


def test_a_damaged_pointer_in_the_bucket_is_replaced_by_a_good_publish(tmp_path: Path) -> None:
    meta = _local_index(tmp_path / "artifacts")
    bucket = FakeBucket()
    bucket.objects[POINTER] = b"not json"
    result = publish_index(tmp_path / "artifacts", _store(bucket, tmp_path), bucket)
    assert result == PublishResult("published", meta.build_id)
    assert json.loads(bucket.objects[POINTER])["build_id"] == meta.build_id


@pytest.mark.parametrize(
    ("missing", "message"),
    [
        (INDEX_NAME, "no index.db in the artifact directory"),
        (MANIFEST_NAME, "no index.manifest.json in the artifact directory"),
    ],
)
def test_a_missing_index_or_manifest_is_a_publish_error(
    tmp_path: Path, missing: str, message: str
) -> None:
    _local_index(tmp_path / "artifacts")
    (tmp_path / "artifacts" / missing).unlink()
    bucket = FakeBucket()
    with pytest.raises(PublishError, match=message):
        publish_index(tmp_path / "artifacts", _store(bucket, tmp_path), bucket)
    assert bucket.uploads == []


def test_a_missing_artifact_directory_is_a_publish_error(tmp_path: Path) -> None:
    bucket = FakeBucket()
    with pytest.raises(PublishError, match="artifact directory does not exist"):
        publish_index(tmp_path / "absent", _store(bucket, tmp_path), bucket)
    assert not (tmp_path / "absent").exists()


@pytest.mark.parametrize("manifest_text", ["not json", "[]", '{"build_id": 7}'])
def test_a_malformed_local_manifest_is_a_publish_error(tmp_path: Path, manifest_text: str) -> None:
    _local_index(tmp_path / "artifacts")
    (tmp_path / "artifacts" / MANIFEST_NAME).write_text(manifest_text, encoding="utf-8")
    bucket = FakeBucket()
    with pytest.raises(PublishError, match="local manifest is not valid"):
        publish_index(tmp_path / "artifacts", _store(bucket, tmp_path), bucket)
    assert bucket.uploads == []


def test_a_db_that_differs_from_its_manifest_uploads_nothing(tmp_path: Path) -> None:
    _local_index(tmp_path / "artifacts")
    db = tmp_path / "artifacts" / INDEX_NAME
    db.write_bytes(db.read_bytes() + b"tampered")
    bucket = FakeBucket()
    with pytest.raises(PublishError, match="local index does not match its manifest"):
        publish_index(tmp_path / "artifacts", _store(bucket, tmp_path), bucket)
    assert bucket.uploads == []
    assert POINTER not in bucket.objects


def test_a_failed_db_upload_leaves_the_pointer_on_the_previous_build(tmp_path: Path) -> None:
    first = _local_index(tmp_path / "first")
    _local_index(tmp_path / "second", now=LATER, pages=1)
    bucket = FakeBucket()
    publish_index(tmp_path / "first", _store(bucket, tmp_path), bucket)
    pointer_before = bucket.objects[POINTER]
    bucket.fail_next_upload = True
    with pytest.raises(SimulatedUploadError):
        publish_index(tmp_path / "second", _store(bucket, tmp_path / "again"), bucket)
    assert bucket.objects[POINTER] == pointer_before
    assert json.loads(bucket.objects[POINTER])["build_id"] == first.build_id


def test_a_failed_first_db_upload_writes_no_pointer(tmp_path: Path) -> None:
    _local_index(tmp_path / "artifacts")
    bucket = FakeBucket()
    bucket.fail_next_upload = True
    with pytest.raises(SimulatedUploadError):
        publish_index(tmp_path / "artifacts", _store(bucket, tmp_path), bucket)
    assert POINTER not in bucket.objects


def test_a_failed_publish_leaves_no_staged_copy_in_the_cache(tmp_path: Path) -> None:
    _local_index(tmp_path / "artifacts")
    bucket = FakeBucket()
    bucket.fail_next_upload = True
    store = _store(bucket, tmp_path)
    with pytest.raises(SimulatedUploadError):
        publish_index(tmp_path / "artifacts", store, bucket)
    assert list((tmp_path / "cache").glob(".index.*.tmp")) == []


# --- the CLI subcommand ---------------------------------------------------------------------


class _Cli:
    def __init__(
        self,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        self.capsys = capsys
        self.monkeypatch = monkeypatch
        self.artifacts = tmp_path / "artifacts"
        self.bucket = FakeBucket()
        monkeypatch.setenv("ARTIFACT_DIR", str(self.artifacts))
        monkeypatch.setenv("ARTIFACT_BUCKET", BUCKET_NAME)
        monkeypatch.setenv("ARTIFACT_PREFIX", PREFIX)

    def publish(self, bucket: FakeBucket | None = None) -> tuple[int, str, str]:
        chosen = bucket or self.bucket
        code = main(["publish"], bucket_factory=lambda _name: chosen)
        captured = self.capsys.readouterr()
        return code, captured.out, captured.err


@pytest.fixture
def cli(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> _Cli:
    caplog.set_level(logging.INFO)
    return _Cli(capsys, monkeypatch, tmp_path)


def _error_lines(err: str) -> list[str]:
    return [line for line in err.splitlines() if line.startswith("ERROR")]


def test_publish_prints_one_published_line_then_one_unchanged_line(cli: _Cli) -> None:
    meta = _local_index(cli.artifacts)
    code, out, err = cli.publish()
    assert (code, out) == (0, f"published build_id={meta.build_id}\n")
    assert _error_lines(err) == []
    code, out, _err = cli.publish()
    assert (code, out) == (0, f"unchanged build_id={meta.build_id}\n")
    assert cli.bucket.uploads.count(POINTER) == 1


def test_publish_prefix_defaults_to_the_bucket_root(
    cli: _Cli, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("ARTIFACT_PREFIX")
    meta = _local_index(cli.artifacts)
    code, out, _err = cli.publish()
    assert (code, out) == (0, f"published build_id={meta.build_id}\n")
    assert MANIFEST_NAME in cli.bucket.objects


@pytest.mark.parametrize(
    ("variable", "bad"),
    [("ARTIFACT_BUCKET", "Not_A_Bucket!"), ("ARTIFACT_PREFIX", "Index/../x")],
)
def test_an_invalid_bucket_or_prefix_names_the_variable_only(
    cli: _Cli, monkeypatch: pytest.MonkeyPatch, variable: str, bad: str
) -> None:
    _local_index(cli.artifacts)
    monkeypatch.setenv(variable, bad)
    code, out, err = cli.publish()
    assert (code, out) == (1, "")
    (line,) = _error_lines(err)
    assert variable in line
    assert bad not in err
    assert cli.bucket.uploads == []


def test_a_missing_bucket_variable_names_it(cli: _Cli, monkeypatch: pytest.MonkeyPatch) -> None:
    _local_index(cli.artifacts)
    monkeypatch.delenv("ARTIFACT_BUCKET")
    code, _out, err = cli.publish()
    assert code == 1
    (line,) = _error_lines(err)
    assert "ARTIFACT_BUCKET" in line


def test_publish_without_an_index_reports_one_error_line(cli: _Cli) -> None:
    code, out, err = cli.publish()
    assert (code, out) == (1, "")
    (line,) = _error_lines(err)
    assert line.startswith("ERROR buddy_sync PublishError")
    assert cli.bucket.uploads == []


def test_publish_with_a_tampered_db_reports_one_error_line(cli: _Cli) -> None:
    _local_index(cli.artifacts)
    db = cli.artifacts / INDEX_NAME
    db.write_bytes(db.read_bytes() + b"tampered")
    code, _out, err = cli.publish()
    assert code == 1
    (line,) = _error_lines(err)
    assert "local index does not match its manifest" in line
    assert cli.bucket.uploads == []


class _FailingBucket(FakeBucket):
    """A bucket whose db upload fails the way the real adapter reports it: a type name."""

    def upload_file(
        self,
        src: Path,
        name: str,
        *,
        content_type: str,
        content_disposition: str | None = None,
        cache_control: str | None = None,
    ) -> None:
        raise BucketError("ServiceUnavailable")


def test_a_failing_bucket_call_is_one_error_line_and_writes_no_pointer(cli: _Cli) -> None:
    _local_index(cli.artifacts)
    bucket = _FailingBucket()
    code, out, err = cli.publish(bucket)
    assert (code, out) == (1, "")
    (line,) = _error_lines(err)
    assert line == "ERROR buddy_sync BucketError: ServiceUnavailable"
    assert POINTER not in bucket.objects


def test_publish_leaves_the_local_artifact_directory_untouched(cli: _Cli) -> None:
    _local_index(cli.artifacts)
    before = {p.name: p.read_bytes() for p in cli.artifacts.iterdir()}
    cli.publish()
    after = {p.name: p.read_bytes() for p in cli.artifacts.iterdir()}
    assert after == before
