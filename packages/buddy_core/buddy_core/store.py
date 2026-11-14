"""ArtifactStore port, its local-directory adapter (D-12) and the bucket adapter (D-06)."""

import base64
import hashlib
import json
import os
import re
import uuid
from pathlib import Path
from typing import Any, Final, Protocol

from buddy_core.models import IndexMeta

INDEX_NAME: Final[str] = "index.db"
MANIFEST_NAME: Final[str] = "index.manifest.json"

_SQLITE_CONTENT_TYPE: Final[str] = "application/vnd.sqlite3"
_JSON_CONTENT_TYPE: Final[str] = "application/json"
_HASH_CHUNK: Final[int] = 1024 * 1024
# GCS bucket naming: 3-63 characters of a-z, 0-9, dot, dash, underscore; alphanumeric at both ends.
_BUCKET_NAME = re.compile(r"[a-z0-9][a-z0-9._-]{1,61}[a-z0-9]")
# An object prefix is empty or lowercase segments, each ending with "/".
_PREFIX_SEGMENT = re.compile(r"[a-z0-9._-]+/")
# build_id becomes part of an object name and of a cache file name: no separator, no dot.
_BUILD_ID = re.compile(r"[A-Za-z0-9_-]{1,128}")
_SHA256 = re.compile(r"[0-9a-f]{64}")


def check_bucket_name(value: str) -> str:
    """Return ``value`` when it is a GCS bucket name; the error never echoes the value."""
    if not _BUCKET_NAME.fullmatch(value) or ".." in value:
        raise ValueError("bucket name must be a lowercase GCS bucket name")
    return value


def check_object_prefix(value: str) -> str:
    """Return ``value`` when it is empty or lowercase ``segment/`` parts; never echoes it."""
    if value == "":
        return value
    body = value[:-1] if value.endswith("/") else None
    segments = body.split("/") if body is not None else []
    valid = (
        body is not None
        and all(_PREFIX_SEGMENT.fullmatch(f"{segment}/") for segment in segments)
        and not any(segment.strip(".") == "" for segment in segments)
        and ".." not in value
    )
    if not valid:
        raise ValueError("object prefix must be empty or lowercase segments each ending with /")
    return value


class ArtifactStore(Protocol):
    """Where a published index artifact lives; adapters hide the location."""

    def latest_path(self) -> Path | None: ...

    def staging_path(self) -> Path: ...

    def publish(self, staged: Path, meta: IndexMeta) -> Path: ...

    def discard(self, staged: Path) -> None: ...


class LocalDirArtifactStore:
    """Single-writer store in one directory; publish is an atomic os.replace."""

    def __init__(self, root: Path) -> None:
        self._root = root
        root.mkdir(parents=True, exist_ok=True)

    def latest_path(self) -> Path | None:
        path = self._root / INDEX_NAME
        return path if path.is_file() else None

    def staging_path(self) -> Path:
        for stale in self._root.glob(".index.*.tmp"):
            stale.unlink(missing_ok=True)
        return self._root / f".index.{uuid.uuid4().hex}.tmp"

    def publish(self, staged: Path, meta: IndexMeta) -> Path:
        data = staged.read_bytes()
        manifest = {
            "schema_version": meta.schema_version,
            "build_id": meta.build_id,
            "content_hash": meta.content_hash,
            "created_at_utc": meta.created_at_utc,
            "sha256": hashlib.sha256(data).hexdigest(),
            "size_bytes": len(data),
        }
        final = self._root / INDEX_NAME
        os.replace(staged, final)
        manifest_tmp = self._root / f".index.{uuid.uuid4().hex}.tmp"
        manifest_tmp.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
        os.replace(manifest_tmp, self._root / MANIFEST_NAME)
        return final

    def discard(self, staged: Path) -> None:
        staged.unlink(missing_ok=True)


class ArtifactIntegrityError(Exception):
    """A published artifact cannot be trusted; messages are fixed text, never object content."""


class BucketPort(Protocol):
    """The object-storage calls GcsArtifactStore needs; one real adapter, one test fake."""

    def read_bytes(self, name: str) -> bytes | None:
        """Object content, or None when the object does not exist."""
        ...

    def download_to(self, name: str, dest: Path) -> None:
        """Write the object to ``dest``; raise FileNotFoundError when it does not exist."""
        ...

    def upload_file(
        self,
        src: Path,
        name: str,
        *,
        content_type: str,
        content_disposition: str | None = None,
        cache_control: str | None = None,
    ) -> None: ...

    def upload_bytes(self, data: bytes, name: str, *, content_type: str) -> None: ...

    def md5_base64(self, name: str) -> str | None:
        """Base64 md5 digest the bucket reports for the object, or None when absent."""
        ...


def _sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(_HASH_CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


class _Pointer:
    """The validated content of ``index.manifest.json`` in the bucket."""

    def __init__(self, raw: bytes) -> None:
        try:
            parsed: Any = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            raise ArtifactIntegrityError("index pointer is not valid JSON") from None
        if not isinstance(parsed, dict):
            raise ArtifactIntegrityError("index pointer is not a JSON object")
        build_id = parsed.get("build_id")
        sha256 = parsed.get("sha256")
        size = parsed.get("size_bytes")
        if not (isinstance(build_id, str) and _BUILD_ID.fullmatch(build_id)):
            raise ArtifactIntegrityError("index pointer has an invalid build_id")
        if not (isinstance(sha256, str) and _SHA256.fullmatch(sha256)):
            raise ArtifactIntegrityError("index pointer has an invalid sha256")
        if not (isinstance(size, int) and not isinstance(size, bool) and size >= 0):
            raise ArtifactIntegrityError("index pointer has an invalid size_bytes")
        if parsed.get("object") != _object_name(build_id):
            raise ArtifactIntegrityError("index pointer names an unexpected object")
        self.build_id = build_id
        self.object_name = _object_name(build_id)
        self.sha256 = sha256
        self.size_bytes = size

    def matches(self, path: Path) -> bool:
        return path.stat().st_size == self.size_bytes and _sha256_of(path) == self.sha256


def _object_name(build_id: str) -> str:
    return f"index-{build_id}.db"


class GcsArtifactStore:
    """Bucket-backed store: ``<prefix>index-<build_id>.db`` plus a pointer.

    publish uploads the db object first and overwrites the pointer last, so a reader that follows
    the pointer never meets a missing or half-written db object. Readers keep a disposable local
    cache of the build the pointer names (the instance holds no state a peer could lack).
    """

    def __init__(self, bucket: BucketPort, prefix: str, cache_dir: Path) -> None:
        self._bucket = bucket
        self._prefix = check_object_prefix(prefix)
        self._cache_dir = cache_dir

    def latest_path(self) -> Path | None:
        raw = self._bucket.read_bytes(self._prefix + MANIFEST_NAME)
        if raw is None:
            return None
        pointer = _Pointer(raw)
        final = self._cache_dir / pointer.object_name
        if final.is_file() and pointer.matches(final):
            return final
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        tmp = self._cache_dir / f".dl.{uuid.uuid4().hex}.tmp"
        try:
            try:
                self._bucket.download_to(self._prefix + pointer.object_name, tmp)
            except FileNotFoundError:
                raise ArtifactIntegrityError(
                    "index object named by the pointer is missing"
                ) from None
            if not pointer.matches(tmp):
                raise ArtifactIntegrityError("index checksum mismatch")
            os.replace(tmp, final)
        finally:
            tmp.unlink(missing_ok=True)
        return final

    def staging_path(self) -> Path:
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        for stale in self._cache_dir.glob(".index.*.tmp"):
            stale.unlink(missing_ok=True)
        return self._cache_dir / f".index.{uuid.uuid4().hex}.tmp"

    def publish(self, staged: Path, meta: IndexMeta) -> Path:
        if not _BUILD_ID.fullmatch(meta.build_id):
            raise ArtifactIntegrityError("build id is not a safe object name")
        data = staged.read_bytes()
        object_name = _object_name(meta.build_id)
        # 1. The db object. A failure here leaves the pointer, and every reader, on the old build.
        self._bucket.upload_file(
            staged, self._prefix + object_name, content_type=_SQLITE_CONTENT_TYPE
        )
        stored_md5 = self._bucket.md5_base64(self._prefix + object_name)
        local_md5 = base64.b64encode(hashlib.md5(data, usedforsecurity=False).digest()).decode(
            "ascii"
        )
        if stored_md5 is not None and stored_md5 != local_md5:
            raise ArtifactIntegrityError("index checksum mismatch")
        pointer = {
            "schema_version": meta.schema_version,
            "build_id": meta.build_id,
            "content_hash": meta.content_hash,
            "created_at_utc": meta.created_at_utc,
            "sha256": hashlib.sha256(data).hexdigest(),
            "size_bytes": len(data),
            "object": object_name,
        }
        # 2. The pointer, last: only now does a reader see the new build.
        self._bucket.upload_bytes(
            json.dumps(pointer, indent=2, sort_keys=True).encode("utf-8"),
            self._prefix + MANIFEST_NAME,
            content_type=_JSON_CONTENT_TYPE,
        )
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        final = self._cache_dir / object_name
        os.replace(staged, final)
        return final

    def discard(self, staged: Path) -> None:
        staged.unlink(missing_ok=True)
