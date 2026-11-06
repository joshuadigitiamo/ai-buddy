"""Cold-start load of the published index artifact (P1 D-11: no hot reload).

The server only reads the artifact. It never creates, stages or publishes anything in the
artifact directory.
"""

import sqlite3
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from buddy_core.index_reader import IndexReader, open_index, to_match_query
from buddy_core.models import GuideChunk, HandbookPage, IndexMeta, VideoLink
from buddy_core.store import LocalDirArtifactStore
from buddy_mcp.stemming import stem_query, stem_text


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


def resolve_index_path(artifact_dir: Path) -> Path:
    """Return the published index.db path; never creates the directory."""
    # LocalDirArtifactStore.__init__ runs mkdir, so the directory is checked first.
    if not artifact_dir.is_dir():
        raise SnapshotError("artifact directory does not exist")
    path = LocalDirArtifactStore(artifact_dir).latest_path()
    if path is None:
        raise SnapshotError("no index.db in artifact directory")
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
