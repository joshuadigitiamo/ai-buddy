"""The empty-context fixture: committed unrelated sources built into a reproducible index (D-16).

`jobs/eval/fixtures/empty_context/fixture.yaml` holds a few synthetic mycology pages (Italian) and
celestial-mechanics chunks (English). `build_fixture` turns them into a schema-valid `index.db`
through the same store and writer the sync job uses, with a fixed build time, so the same sources
always give the same content hash. The index is never committed: `*.db` is gitignored and
dockerignored, so it is built from the sources whenever the eval profile starts.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

import yaml

from buddy_core.index_writer import build_index
from buddy_core.models import GuideChunk, HandbookPage, IndexContent, IndexMeta, make_chunk_key
from buddy_core.store import LocalDirArtifactStore

FIXTURE_NOW: Final = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)
FIXTURE_PATH: Final = (
    Path(__file__).resolve().parents[1] / "fixtures" / "empty_context" / "fixture.yaml"
)
SCHEMA_VERSION: Final = 1
SOURCE_DOC_ID: Final = "eval-empty-fixture"
GUIDES_COMMIT_SHA: Final = "0" * 40
FIXTURE_VERSION: Final = "eval-fixture-1"


class FixtureError(ValueError):
    """The fixture sources are unreadable or malformed; the message names the field."""


def _mapping(value: object, where: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise FixtureError(f"{where}: expected a mapping")
    return value


def _text(entry: Mapping[str, Any], key: str, where: str) -> str:
    value = entry.get(key)
    if not isinstance(value, str) or not value.strip():
        raise FixtureError(f"{where}: {key} must be non-empty text")
    return value.strip()


def _integer(entry: Mapping[str, Any], key: str, where: str) -> int:
    value = entry.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise FixtureError(f"{where}: {key} must be a positive integer")
    return value


def _entries(raw: Mapping[str, Any], key: str) -> list[Mapping[str, Any]]:
    value = raw.get(key)
    if not isinstance(value, list) or not value:
        raise FixtureError(f"{key}: expected a non-empty list")
    return [_mapping(entry, f"{key}[{position}]") for position, entry in enumerate(value)]


def _page(position: int, entry: Mapping[str, Any]) -> HandbookPage:
    where = f"pages[{position}]"
    page_id = _text(entry, "page_id", where)
    text = _text(entry, "text", where)
    # YAML turns an unquoted date into a date object: str() covers both spellings.
    updated = str(entry.get("last_updated", "")).strip()
    if not updated:
        raise FixtureError(f"{where}: last_updated must be an ISO date")
    return HandbookPage(
        page_id=page_id,
        parent_id=None,
        position=position,
        depth=0,
        title=_text(entry, "title", where),
        url=f"handbook://{page_id}",
        date_edited_raw=None,
        date_created_raw=None,
        revision_date_iso=f"{updated}T00:00:00+00:00",
        content_md=text,
        content_hash=hashlib.sha256(text.encode("utf-8")).hexdigest(),
    )


def _chunk(position: int, entry: Mapping[str, Any]) -> GuideChunk:
    where = f"chunks[{position}]"
    file = _text(entry, "file", where)
    h2 = _text(entry, "h2", where)
    h3_raw = entry.get("h3")
    h3 = None if h3_raw is None else _text(entry, "h3", where)
    return GuideChunk(
        chunk_key=make_chunk_key(file, h2, h3, 0),
        file=file,
        h2=h2,
        h3=h3,
        heading=h3 or h2,
        line_start=_integer(entry, "line_start", where),
        line_end=_integer(entry, "line_end", where),
        part_index=0,
        text=_text(entry, "text", where),
    )


def build_fixture_content(path: Path = FIXTURE_PATH) -> IndexContent:
    """Parse the fixture sources into index content; a bad file raises FixtureError."""
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise FixtureError(f"{path.name}: not valid YAML ({type(exc).__name__})") from exc
    raw = _mapping(loaded, path.name)
    if raw.get("schema_version") != SCHEMA_VERSION:
        raise FixtureError(f"{path.name}: schema_version must be {SCHEMA_VERSION}")
    return IndexContent(
        handbook=tuple(_page(i, e) for i, e in enumerate(_entries(raw, "pages"))),
        chunks=tuple(_chunk(i, e) for i, e in enumerate(_entries(raw, "chunks"))),
        videos={},
        source_doc_id=SOURCE_DOC_ID,
        guides_commit_sha=GUIDES_COMMIT_SHA,
        pipeline_version=FIXTURE_VERSION,
        redaction_version=FIXTURE_VERSION,
    )


def build_fixture(dest: Path, source: Path = FIXTURE_PATH) -> IndexMeta:
    """Stage, build and publish the fixture index under `dest`; return its meta."""
    content = build_fixture_content(source)
    store = LocalDirArtifactStore(dest)
    staged = store.staging_path()
    try:
        meta = build_index(content, staged, now=FIXTURE_NOW)
        store.publish(staged, meta)
    finally:
        store.discard(staged)
    return meta
