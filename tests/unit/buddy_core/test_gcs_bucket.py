"""GcsBucket against a stand-in storage client: calls, NotFound mapping, safe errors. No network."""

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from google.api_core.exceptions import Forbidden, NotFound, ServiceUnavailable

from buddy_core.gcs_bucket import BucketError, GcsBucket

SECRET = "token=sentinel-secret-5d2e https://storage.example.invalid/b/o"


def _bucket() -> tuple[GcsBucket, MagicMock, MagicMock]:
    """A GcsBucket over a mock client; returns it with the client and the blob it hands out."""
    client = MagicMock(name="client")
    blob = MagicMock(name="blob")
    client.bucket.return_value.blob.return_value = blob
    return GcsBucket("bucket-x", client_factory=lambda: client), client, blob


def _err(kind: type[Exception], message: str = "gone") -> Exception:
    """Build a storage error through a typed callable (api_core constructors carry no hints)."""
    return kind(message)


def _raise(error: Exception) -> Any:
    def boom(*args: Any, **kwargs: Any) -> Any:
        raise error

    return boom


def test_construction_builds_no_client() -> None:
    built: list[str] = []

    def factory() -> Any:
        built.append("client")
        return MagicMock()

    GcsBucket("bucket-x", client_factory=factory)

    assert built == []


def test_the_client_is_built_once_and_reused() -> None:
    built: list[str] = []
    client = MagicMock()

    def factory() -> Any:
        built.append("client")
        return client

    bucket = GcsBucket("bucket-x", client_factory=factory)
    bucket.read_bytes("a")
    bucket.read_bytes("b")

    assert built == ["client"]
    client.bucket.assert_called_with("bucket-x")


def test_read_bytes_returns_the_object_content() -> None:
    bucket, client, blob = _bucket()
    blob.download_as_bytes.return_value = b"pointer"

    assert bucket.read_bytes("idx/index.manifest.json") == b"pointer"
    client.bucket.return_value.blob.assert_called_once_with("idx/index.manifest.json")


def test_read_bytes_of_a_missing_object_is_none() -> None:
    bucket, _client, blob = _bucket()
    blob.download_as_bytes.side_effect = _err(NotFound)

    assert bucket.read_bytes("nope") is None


def test_download_to_writes_to_the_destination(tmp_path: Path) -> None:
    bucket, _client, blob = _bucket()
    dest = tmp_path / "out.db"

    bucket.download_to("idx/index-x.db", dest)

    blob.download_to_filename.assert_called_once_with(str(dest))


def test_download_to_of_a_missing_object_is_file_not_found(tmp_path: Path) -> None:
    bucket, _client, blob = _bucket()
    blob.download_to_filename.side_effect = _err(NotFound)

    with pytest.raises(FileNotFoundError):
        bucket.download_to("nope", tmp_path / "out.db")


def test_download_to_a_missing_local_directory_is_a_bucket_error(tmp_path: Path) -> None:
    bucket, _client, blob = _bucket()
    blob.download_to_filename.side_effect = FileNotFoundError(str(tmp_path / "gone" / "x"))

    with pytest.raises(BucketError) as caught:
        bucket.download_to("idx/index-x.db", tmp_path / "gone" / "x")
    assert str(caught.value) == "FileNotFoundError"


def test_upload_file_sets_content_type_only_by_default(tmp_path: Path) -> None:
    bucket, _client, blob = _bucket()
    src = tmp_path / "index.db"
    src.write_bytes(b"db")
    # A MagicMock would invent attributes: pin the ones the call must leave untouched.
    blob.content_disposition = None
    blob.cache_control = None

    bucket.upload_file(src, "idx/index-x.db", content_type="application/vnd.sqlite3")

    blob.upload_from_filename.assert_called_once_with(
        str(src), content_type="application/vnd.sqlite3"
    )
    assert blob.content_disposition is None
    assert blob.cache_control is None


def test_upload_file_sets_disposition_and_cache_control_before_the_upload(tmp_path: Path) -> None:
    bucket, _client, blob = _bucket()
    src = tmp_path / "video.mp4"
    src.write_bytes(b"mp4")
    seen: dict[str, Any] = {}

    def upload(filename: str, content_type: str) -> None:
        seen["disposition"] = blob.content_disposition
        seen["cache"] = blob.cache_control
        seen["content_type"] = content_type

    blob.upload_from_filename.side_effect = upload

    bucket.upload_file(
        src,
        "videos/a.mp4",
        content_type="video/mp4",
        content_disposition="inline",
        cache_control="private, max-age=60",
    )

    assert seen == {
        "disposition": "inline",
        "cache": "private, max-age=60",
        "content_type": "video/mp4",
    }


def test_upload_bytes_sends_the_data_with_its_content_type() -> None:
    bucket, _client, blob = _bucket()

    bucket.upload_bytes(b"{}", "idx/index.manifest.json", content_type="application/json")

    blob.upload_from_string.assert_called_once_with(b"{}", content_type="application/json")


def test_md5_base64_reloads_then_reports_the_digest() -> None:
    bucket, _client, blob = _bucket()
    blob.md5_hash = "1B2M2Y8AsgTpgAmY7PhCfg=="

    assert bucket.md5_base64("idx/index-x.db") == "1B2M2Y8AsgTpgAmY7PhCfg=="
    blob.reload.assert_called_once_with()


def test_md5_base64_of_a_missing_object_is_none() -> None:
    bucket, _client, blob = _bucket()
    blob.reload.side_effect = _err(NotFound)

    assert bucket.md5_base64("nope") is None


def test_md5_base64_without_a_digest_is_none() -> None:
    bucket, _client, blob = _bucket()
    blob.md5_hash = None

    assert bucket.md5_base64("idx/index-x.db") is None


@pytest.mark.parametrize(
    ("method", "call"),
    [
        ("download_as_bytes", lambda b, _p: b.read_bytes("x")),
        ("download_to_filename", lambda b, p: b.download_to("x", p / "o")),
        ("upload_from_filename", lambda b, p: b.upload_file(p / "s", "x", content_type="t")),
        ("upload_from_string", lambda b, _p: b.upload_bytes(b"d", "x", content_type="t")),
        ("reload", lambda b, _p: b.md5_base64("x")),
    ],
)
@pytest.mark.parametrize("kind", [Forbidden, ServiceUnavailable, OSError])
def test_storage_errors_surface_as_the_type_name_only(
    tmp_path: Path, method: str, call: Any, kind: type[Exception]
) -> None:
    bucket, _client, blob = _bucket()
    error = _err(kind, SECRET)
    getattr(blob, method).side_effect = _raise(error)

    with pytest.raises(BucketError) as caught:
        call(bucket, tmp_path)

    assert str(caught.value) == type(error).__name__
    assert caught.value.__cause__ is None
    assert caught.value.__suppress_context__ is True
    assert "sentinel-secret" not in repr(caught.value)


def test_client_construction_failure_is_a_bucket_error_without_its_message() -> None:
    class CredentialsMissing(OSError):
        pass

    def factory() -> Any:
        raise CredentialsMissing(SECRET)

    bucket = GcsBucket("bucket-x", client_factory=factory)

    with pytest.raises(BucketError) as caught:
        bucket.read_bytes("x")
    assert str(caught.value) == "CredentialsMissing"
