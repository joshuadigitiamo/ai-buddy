"""Build an index.db artifact from logical content (D-08, D-09)."""

import hashlib
import json
import sqlite3
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from buddy_core.models import IndexContent, IndexMeta
from buddy_core.schema import SCHEMA_MAJOR, SCHEMA_VERSION, create_schema


def compute_content_hash(content: IndexContent) -> str:
    """sha256 over canonical JSON of the logical rows.

    The hash never covers SQLite file bytes, build_id or timestamps, so identical content
    always yields an identical hash (D-09).
    """
    payload = {
        "schema_version": SCHEMA_VERSION,
        "source_doc_id": content.source_doc_id,
        "guides_commit_sha": content.guides_commit_sha,
        "pipeline_version": content.pipeline_version,
        "redaction_version": content.redaction_version,
        "handbook": [asdict(p) for p in sorted(content.handbook, key=lambda p: p.page_id)],
        "chunks": [asdict(c) for c in sorted(content.chunks, key=lambda c: c.chunk_key)],
        "videos": [
            {"chunk_key": key, **asdict(content.videos[key])} for key in sorted(content.videos)
        ],
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def make_build_id(now: datetime, content_hash: str) -> str:
    """UTC timestamp plus the first 12 hex characters of the content hash (D-09)."""
    stamp = now.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"{stamp}-{content_hash[:12]}"


def _validate(content: IndexContent) -> None:
    chunk_keys = {c.chunk_key for c in content.chunks}
    if len(chunk_keys) != len(content.chunks):
        raise ValueError("duplicate chunk_key in content")
    unknown = sorted(set(content.videos) - chunk_keys)
    if unknown:
        raise ValueError(f"video map names chunk keys that do not exist: {unknown}")
    positions = [p.position for p in content.handbook]
    if len(set(positions)) != len(positions):
        raise ValueError("handbook positions repeat")


def build_index(content: IndexContent, dest: Path, *, now: datetime) -> IndexMeta:
    """Write a complete, single-file index.db at `dest` (which must not exist)."""
    if dest.exists():
        raise FileExistsError(str(dest))
    _validate(content)
    content_hash = compute_content_hash(content)
    meta = IndexMeta(
        schema_version=SCHEMA_VERSION,
        build_id=make_build_id(now, content_hash),
        content_hash=content_hash,
        guides_commit_sha=content.guides_commit_sha,
        source_doc_id=content.source_doc_id,
        pipeline_version=content.pipeline_version,
        redaction_version=content.redaction_version,
        created_at_utc=now.astimezone(UTC).isoformat(),
    )
    conn = sqlite3.connect(dest)
    try:
        conn.execute("PRAGMA journal_mode=DELETE")
        create_schema(conn)
        conn.executemany(
            "INSERT INTO handbook_pages (page_id, parent_id, position, depth, title, url,"
            " date_edited_raw, date_created_raw, revision_date_iso, content_md, content_hash)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    p.page_id,
                    p.parent_id,
                    p.position,
                    p.depth,
                    p.title,
                    p.url,
                    p.date_edited_raw,
                    p.date_created_raw,
                    p.revision_date_iso,
                    p.content_md,
                    p.content_hash,
                )
                for p in sorted(content.handbook, key=lambda p: p.position)
            ],
        )
        ordered = sorted(content.chunks, key=lambda c: (c.file, c.line_start, c.part_index))
        conn.executemany(
            "INSERT INTO guide_chunks (id, chunk_key, file, h2, h3, heading, line_start,"
            " line_end, part_index, text) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    idx,
                    c.chunk_key,
                    c.file,
                    c.h2,
                    c.h3,
                    c.heading,
                    c.line_start,
                    c.line_end,
                    c.part_index,
                    c.text,
                )
                for idx, c in enumerate(ordered, start=1)
            ],
        )
        conn.executemany(
            "INSERT INTO video_map (chunk_key, video_url, part, start_seconds, source)"
            " VALUES (?, ?, ?, ?, ?)",
            [
                (key, v.video_url, v.part, v.start_seconds, v.source)
                for key, v in sorted(content.videos.items())
            ],
        )
        conn.execute("INSERT INTO guide_chunks_fts(guide_chunks_fts) VALUES ('rebuild')")
        conn.executemany(
            "INSERT INTO meta (key, value) VALUES (?, ?)",
            [
                ("schema_version", meta.schema_version),
                ("build_id", meta.build_id),
                ("content_hash", meta.content_hash),
                ("guides_commit_sha", meta.guides_commit_sha),
                ("source_doc_id", meta.source_doc_id),
                ("pipeline_version", meta.pipeline_version),
                ("redaction_version", meta.redaction_version),
                ("created_at_utc", meta.created_at_utc),
            ],
        )
        conn.execute(f"PRAGMA user_version = {int(SCHEMA_MAJOR)}")
        conn.commit()
        conn.execute("VACUUM")
    finally:
        conn.close()
    return meta
