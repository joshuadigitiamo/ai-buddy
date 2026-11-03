"""ArtifactStore port and its local-directory adapter (D-12)."""

import hashlib
import json
import os
import uuid
from pathlib import Path
from typing import Final, Protocol

from buddy_core.models import IndexMeta

INDEX_NAME: Final[str] = "index.db"
MANIFEST_NAME: Final[str] = "index.manifest.json"


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
