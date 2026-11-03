"""index.db schema (D-08). A major bump of SCHEMA_VERSION is a breaking contract change."""

import sqlite3
from typing import Final

SCHEMA_VERSION = "1.0.0"
SCHEMA_MAJOR = 1

META_KEYS: Final[tuple[str, ...]] = (
    "schema_version",
    "build_id",
    "content_hash",
    "guides_commit_sha",
    "source_doc_id",
    "pipeline_version",
    "redaction_version",
    "created_at_utc",
)

DDL: Final[tuple[str, ...]] = (
    "CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)",
    """CREATE TABLE handbook_pages (
        page_id TEXT PRIMARY KEY,
        parent_id TEXT,
        position INTEGER NOT NULL UNIQUE,
        depth INTEGER NOT NULL,
        title TEXT NOT NULL,
        url TEXT NOT NULL,
        date_edited_raw INTEGER,
        date_created_raw INTEGER,
        revision_date_iso TEXT,
        content_md TEXT NOT NULL,
        content_hash TEXT NOT NULL
    )""",
    """CREATE TABLE guide_chunks (
        id INTEGER PRIMARY KEY,
        chunk_key TEXT NOT NULL UNIQUE,
        file TEXT NOT NULL,
        h2 TEXT NOT NULL,
        h3 TEXT,
        heading TEXT NOT NULL,
        line_start INTEGER NOT NULL,
        line_end INTEGER NOT NULL,
        part_index INTEGER NOT NULL,
        text TEXT NOT NULL
    )""",
    """CREATE VIRTUAL TABLE guide_chunks_fts USING fts5(
        h2, heading, text,
        content='guide_chunks', content_rowid='id',
        tokenize='porter unicode61 remove_diacritics 2'
    )""",
    """CREATE TABLE video_map (
        chunk_key TEXT PRIMARY KEY REFERENCES guide_chunks(chunk_key),
        video_url TEXT NOT NULL,
        part INTEGER NOT NULL,
        start_seconds REAL,
        source TEXT NOT NULL CHECK (source IN ('scene', 'readme_fallback'))
    )""",
)


def create_schema(conn: sqlite3.Connection) -> None:
    """Create every table of the contract in an empty database."""
    for statement in DDL:
        conn.execute(statement)
