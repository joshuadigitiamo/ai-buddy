"""Cold-start load of the published index artifact (P1 D-11: no hot reload).

The server only reads the artifact. It never creates, stages or publishes anything in the
artifact directory.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from buddy_core.index_reader import IndexReader, open_index
from buddy_core.models import GuideChunk, HandbookPage, IndexMeta, VideoLink
from buddy_core.store import LocalDirArtifactStore


class SnapshotError(Exception):
    """The artifact cannot be served; messages hold fixed text and page ids only."""


@dataclass(frozen=True, slots=True)
class IndexSnapshot:
    """The read-only in-memory view every tool serves from."""

    meta: IndexMeta
    pages: Mapping[str, HandbookPage]
    chunks: Mapping[str, GuideChunk]
    videos: Mapping[str, VideoLink]
    reader: IndexReader


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
        )
    except BaseException:
        reader.close()
        raise
