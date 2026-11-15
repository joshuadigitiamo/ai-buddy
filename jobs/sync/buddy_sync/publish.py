"""Publish the local ``index.db`` to the private bucket (D-06).

The sync writes ``index.db`` and ``index.manifest.json`` into ``ARTIFACT_DIR``. ``publish_index``
checks them against each other, then hands the file to ``GcsArtifactStore``, which uploads the db
object first and overwrites the bucket pointer last. The function takes the store and the bucket
port, so tests use a fake bucket and only the CLI builds the real adapters.
"""

from __future__ import annotations

import base64
import hashlib
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Literal

from buddy_core.index_reader import open_index
from buddy_core.store import INDEX_NAME, MANIFEST_NAME, BucketPort, GcsArtifactStore

_HASH_CHUNK: Final = 1024 * 1024
_STRING_KEYS: Final = ("build_id", "content_hash", "sha256")


class PublishError(Exception):
    """The local index cannot be published; messages are fixed text, never file content."""


@dataclass(frozen=True, slots=True)
class PublishResult:
    """What a publish did: a new build went out, or the bucket already held this content."""

    status: Literal["published", "unchanged"]
    build_id: str


def _sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(_HASH_CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


def _md5_base64_of(path: Path) -> str:
    digest = hashlib.md5(usedforsecurity=False)
    with path.open("rb") as handle:
        while chunk := handle.read(_HASH_CHUNK):
            digest.update(chunk)
    return base64.b64encode(digest.digest()).decode("ascii")


def _load_local_manifest(path: Path) -> dict[str, Any]:
    try:
        parsed: Any = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise PublishError("local manifest is not valid") from None
    size = parsed.get("size_bytes") if isinstance(parsed, dict) else None
    valid = (
        isinstance(parsed, dict)
        and all(isinstance(parsed.get(key), str) and parsed[key] for key in _STRING_KEYS)
        and isinstance(size, int)
        and not isinstance(size, bool)
    )
    if not valid:
        raise PublishError("local manifest is not valid")
    manifest: dict[str, Any] = parsed
    return manifest


def _bucket_pointer(bucket: BucketPort, name: str) -> dict[str, Any] | None:
    """The pointer the bucket holds, or None when it is absent or unusable.

    An unusable pointer is not an error here: a good publish is exactly what replaces it.
    """
    raw = bucket.read_bytes(name)
    if raw is None:
        return None
    try:
        parsed: Any = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return None
    if not isinstance(parsed, dict):
        return None
    pointer: dict[str, Any] = parsed
    return pointer


def _pointer_object_is_current(
    bucket: BucketPort,
    store: GcsArtifactStore,
    pointer: dict[str, Any],
    manifest: dict[str, Any],
    db_path: Path,
) -> bool:
    """True when the db object the pointer names exists in the bucket and can be trusted.

    A pointer whose object was deleted or damaged would make the server fail at cold start, so
    ``unchanged`` is only honest after this check. For the same build the object must also match
    the local db byte for byte; for another build with the same content, presence is enough.
    """
    build_id = pointer.get("build_id")
    if not isinstance(build_id, str) or not build_id:
        return False
    if pointer.get("object") != f"index-{build_id}.db":
        return False
    stored_md5 = bucket.md5_base64(store.prefix + f"index-{build_id}.db")
    if stored_md5 is None:
        return False
    if build_id == manifest["build_id"]:
        return stored_md5 == _md5_base64_of(db_path)
    return True


def publish_index(local_dir: Path, store: GcsArtifactStore, bucket: BucketPort) -> PublishResult:
    """Publish ``local_dir/index.db`` unless the bucket already serves the same content.

    "Serves" means the pointer has the same content hash and the db object it names is present.
    """
    if not local_dir.is_dir():
        raise PublishError("artifact directory does not exist")
    db_path = local_dir / INDEX_NAME
    manifest_path = local_dir / MANIFEST_NAME
    if not db_path.is_file():
        raise PublishError(f"no {INDEX_NAME} in the artifact directory")
    if not manifest_path.is_file():
        raise PublishError(f"no {MANIFEST_NAME} in the artifact directory")

    manifest = _load_local_manifest(manifest_path)
    if (
        db_path.stat().st_size != manifest["size_bytes"]
        or _sha256_of(db_path) != manifest["sha256"]
    ):
        raise PublishError("local index does not match its manifest")

    pointer = _bucket_pointer(bucket, store.prefix + MANIFEST_NAME)
    if (
        pointer is not None
        and pointer.get("content_hash") == manifest["content_hash"]
        and _pointer_object_is_current(bucket, store, pointer, manifest, db_path)
    ):
        return PublishResult("unchanged", str(pointer["build_id"]))

    with open_index(db_path) as reader:
        meta = reader.meta
    if meta.build_id != manifest["build_id"] or meta.content_hash != manifest["content_hash"]:
        raise PublishError("local index does not match its manifest")

    staged = store.staging_path()
    try:
        shutil.copyfile(db_path, staged)
        store.publish(staged, meta)
    finally:
        store.discard(staged)
    return PublishResult("published", meta.build_id)
