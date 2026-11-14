"""Cold-start load of the published index artifact (P1 D-11: no hot reload).

The server only reads the artifact. It never creates, stages or publishes anything in the
artifact directory. Which store it reads from (a local directory or a bucket) is chosen by
configuration in ``artifact_store_from_settings`` and nowhere else (D-06, D-10).
"""

import sqlite3
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from buddy_core.index_reader import IndexReader, open_index, to_match_query
from buddy_core.models import GuideChunk, HandbookPage, IndexMeta, VideoLink
from buddy_core.store import (
    ArtifactIntegrityError,
    ArtifactStore,
    BucketPort,
    GcsArtifactStore,
    LocalDirArtifactStore,
)
from buddy_mcp.config import McpSettings
from buddy_mcp.stemming import stem_query, stem_text

# Where a bucket-backed server keeps its disposable copy of the index when ARTIFACT_DIR is unset.
DEFAULT_CACHE_DIR: Final = Path("/tmp/buddy-index")

BucketFactory = Callable[[str], BucketPort]


class SnapshotError(Exception):
    """The artifact cannot be served; messages hold fixed text and page ids only."""


class HandbookIndex:
    """In-memory FTS5 table over whole handbook pages, with Italian Snowball stems (D-01, D-02).

    Built once at cold start from handbook_pages; index.db itself is never altered.
    """

    def __init__(self, pages: Sequence[HandbookPage]) -> None:
        # Same loop thread as the async tools, like the Guides reader.
        self._conn = sqlite3.connect(":memory:")
        self._pages = tuple(pages)
        self._conn.execute(
            "CREATE VIRTUAL TABLE pages USING fts5("
            "title, body, tokenize='unicode61 remove_diacritics 2')"
        )
        self._conn.executemany(
            "INSERT INTO pages(rowid, title, body) VALUES (?, ?, ?)",
            [
                (position, " ".join(stem_text(page.title)), " ".join(stem_text(page.content_md)))
                for position, page in enumerate(self._pages)
            ],
        )

    def search(self, query: str, limit: int) -> list[HandbookPage]:
        """Pages matching any stem of `query`, best bm25 first; ties keep page order."""
        expression = to_match_query(" ".join(stem_query(query)))
        if expression is None:
            return []
        rows = self._conn.execute(
            "SELECT rowid FROM pages WHERE pages MATCH ? ORDER BY bm25(pages, 5.0, 1.0), rowid "
            "LIMIT ?",
            (expression, limit),
        ).fetchall()
        return [self._pages[int(row[0])] for row in rows]

    def close(self) -> None:
        self._conn.close()


@dataclass(frozen=True, slots=True)
class IndexSnapshot:
    """The read-only in-memory view every tool serves from."""

    meta: IndexMeta
    pages: Mapping[str, HandbookPage]
    chunks: Mapping[str, GuideChunk]
    videos: Mapping[str, VideoLink]
    reader: IndexReader
    handbook_index: HandbookIndex


def artifact_store_from_settings(
    settings: McpSettings, *, bucket_factory: BucketFactory
) -> ArtifactStore:
    """The store the settings name; a local store never creates its directory."""
    if settings.artifact_store == "gcs":
        bucket_name = settings.artifact_bucket
        if bucket_name is None:  # McpSettings refuses this already; keeps the type honest
            raise SnapshotError("ARTIFACT_BUCKET is not set")
        return GcsArtifactStore(
            bucket_factory(bucket_name),
            settings.artifact_prefix,
            settings.artifact_dir or DEFAULT_CACHE_DIR,
        )
    artifact_dir = settings.artifact_dir
    if artifact_dir is None:  # McpSettings refuses this already; keeps the type honest
        raise SnapshotError("ARTIFACT_DIR is not set")
    # LocalDirArtifactStore.__init__ runs mkdir, so the directory is checked first.
    if not artifact_dir.is_dir():
        raise SnapshotError("artifact directory does not exist")
    return LocalDirArtifactStore(artifact_dir)


def resolve_index_path(store: ArtifactStore) -> Path:
    """Return the published index path the store holds; messages name the store, not a bucket."""
    try:
        path = store.latest_path()
    except ArtifactIntegrityError as exc:
        raise SnapshotError(str(exc)) from None
    if path is None:
        if isinstance(store, LocalDirArtifactStore):
            raise SnapshotError("no index.db in artifact directory")
        raise SnapshotError("no published index in artifact store")
    return path


def load_snapshot(path: Path) -> IndexSnapshot:
    """Open the index once and load pages, chunks and video links into memory."""
    reader = open_index(path)
    try:
        pages = reader.load_handbook()
        # A page without a revision date would make a handbook result uncitable (MCP-03).
        undated = [page.page_id for page in pages if not page.revision_date_iso]
        if undated:
            raise SnapshotError(f"handbook pages without a revision date: {', '.join(undated)}")
        return IndexSnapshot(
            meta=reader.meta,
            pages={page.page_id: page for page in pages},
            chunks={chunk.chunk_key: chunk for chunk in reader.guide_chunks()},
            videos=reader.video_links(),
            reader=reader,
            handbook_index=HandbookIndex(pages),
        )
    except BaseException:
        reader.close()
        raise
