"""Read-only access to an index.db artifact: the only SQL surface consumers use."""

import sqlite3
from pathlib import Path
from types import TracebackType
from typing import Literal, Self, cast

from buddy_core.models import GuideChunk, HandbookPage, IndexMeta, SearchHit, VideoLink
from buddy_core.schema import META_KEYS, SCHEMA_MAJOR

_MAX_LIMIT = 50

_CHUNK_COLUMNS = (
    "c.chunk_key, c.file, c.h2, c.h3, c.heading, c.line_start, c.line_end, c.part_index, c.text"
)


class IndexFormatError(Exception):
    """The artifact is not a well-formed index.db."""


class IndexVersionError(IndexFormatError):
    """The artifact's schema major differs from the one this code understands."""


def to_match_query(query: str) -> str | None:
    """Turn free text into a safe FTS5 MATCH expression, or None when nothing searchable remains.

    Every token becomes a double-quoted phrase, so FTS5 operators and column filters in user
    input are inert.
    """
    # A NUL byte would end the SQL string early; treat it as a separator like whitespace.
    tokens = [t for t in query.replace("\x00", " ").split() if any(ch.isalnum() for ch in t)]
    if not tokens:
        return None
    return " OR ".join('"' + t.replace('"', '""') + '"' for t in tokens)


def _row_to_chunk(row: tuple[object, ...]) -> GuideChunk:
    return GuideChunk(
        chunk_key=cast(str, row[0]),
        file=cast(str, row[1]),
        h2=cast(str, row[2]),
        h3=cast("str | None", row[3]),
        heading=cast(str, row[4]),
        line_start=cast(int, row[5]),
        line_end=cast(int, row[6]),
        part_index=cast(int, row[7]),
        text=cast(str, row[8]),
    )


def _row_to_video(video_url: str, part: int, start: float | None, source: str) -> VideoLink:
    if source not in ("scene", "readme_fallback"):
        raise IndexFormatError(f"unknown video source: {source!r}")
    return VideoLink(
        video_url=video_url,
        part=part,
        start_seconds=start,
        source=cast(Literal["scene", "readme_fallback"], source),
    )


class IndexReader:
    """A read-only view of one artifact."""

    def __init__(self, conn: sqlite3.Connection, meta: IndexMeta) -> None:
        self._conn = conn
        self.meta = meta

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    def _pages(self, where: str, params: tuple[str, ...]) -> list[HandbookPage]:
        rows = self._conn.execute(
            "SELECT page_id, parent_id, position, depth, title, url, date_edited_raw,"
            " date_created_raw, revision_date_iso, content_md, content_hash"
            f" FROM handbook_pages {where} ORDER BY position",
            params,
        ).fetchall()
        return [HandbookPage(*row) for row in rows]

    def load_handbook(self) -> list[HandbookPage]:
        return self._pages("", ())

    def get_page(self, page_id: str) -> HandbookPage | None:
        pages = self._pages("WHERE page_id = ?", (page_id,))
        return pages[0] if pages else None

    def guide_chunks(self) -> list[GuideChunk]:
        rows = self._conn.execute(
            f"SELECT {_CHUNK_COLUMNS} FROM guide_chunks c ORDER BY c.id"
        ).fetchall()
        return [_row_to_chunk(row) for row in rows]

    def video_links(self) -> dict[str, VideoLink]:
        rows = self._conn.execute(
            "SELECT chunk_key, video_url, part, start_seconds, source FROM video_map"
            " ORDER BY chunk_key"
        ).fetchall()
        return {key: _row_to_video(url, part, start, src) for key, url, part, start, src in rows}

    def search_guides(self, query: str, limit: int = 5) -> list[SearchHit]:
        """BM25 keyword search over Guides chunks; never raises on user text."""
        match = to_match_query(query)
        if match is None:
            return []
        limit = max(1, min(limit, _MAX_LIMIT))
        rows = self._conn.execute(
            f"SELECT {_CHUNK_COLUMNS},"
            " bm25(guide_chunks_fts, 4.0, 6.0, 1.0) AS score,"
            " v.video_url, v.part, v.start_seconds, v.source"
            " FROM guide_chunks_fts"
            " JOIN guide_chunks c ON c.id = guide_chunks_fts.rowid"
            " LEFT JOIN video_map v ON v.chunk_key = c.chunk_key"
            " WHERE guide_chunks_fts MATCH ?"
            " ORDER BY score, c.id LIMIT ?",
            (match, limit),
        ).fetchall()
        hits: list[SearchHit] = []
        for row in rows:
            video = _row_to_video(row[10], row[11], row[12], row[13]) if row[10] else None
            hits.append(SearchHit(chunk=_row_to_chunk(row[:9]), score=float(row[9]), video=video))
        return hits


def _read_meta(conn: sqlite3.Connection) -> IndexMeta:
    values = dict(conn.execute("SELECT key, value FROM meta").fetchall())
    missing = [k for k in META_KEYS if k not in values]
    if missing:
        raise IndexFormatError(f"meta is missing keys: {missing}")
    return IndexMeta(**{k: values[k] for k in META_KEYS})


def open_index(path: Path) -> IndexReader:
    """Open an artifact read-only, refusing a different schema major (D-09)."""
    if not path.is_file():
        raise FileNotFoundError(str(path))
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        user_version = int(conn.execute("PRAGMA user_version").fetchone()[0])
        if user_version != SCHEMA_MAJOR:
            raise IndexVersionError(
                f"artifact user_version {user_version}, expected major {SCHEMA_MAJOR}"
            )
        try:
            meta = _read_meta(conn)
        except sqlite3.DatabaseError as exc:
            raise IndexFormatError(f"cannot read meta table: {exc}") from exc
        major_text = meta.schema_version.split(".", 1)[0]
        if not major_text.isdigit() or int(major_text) != SCHEMA_MAJOR:
            raise IndexVersionError(
                f"artifact schema_version {meta.schema_version}, expected major {SCHEMA_MAJOR}"
            )
    except BaseException:
        conn.close()
        raise
    return IndexReader(conn, meta)
