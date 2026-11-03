"""Row models and small helpers for the index.db contract (D-08)."""

import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True, slots=True)
class HandbookPage:
    """One handbook page as stored in handbook_pages."""

    page_id: str
    parent_id: str | None
    position: int
    depth: int
    title: str
    url: str
    date_edited_raw: int | None
    date_created_raw: int | None
    revision_date_iso: str | None
    content_md: str
    content_hash: str


@dataclass(frozen=True, slots=True)
class GuideChunk:
    """One Guides chunk as stored in guide_chunks; lines are 1-based and inclusive."""

    chunk_key: str
    file: str
    h2: str
    h3: str | None
    heading: str
    line_start: int
    line_end: int
    part_index: int
    text: str


@dataclass(frozen=True, slots=True)
class VideoLink:
    """Base video URL plus an optional scene offset, stored separately (D-01)."""

    video_url: str
    part: int
    start_seconds: float | None
    source: Literal["scene", "readme_fallback"]


@dataclass(frozen=True, slots=True)
class IndexContent:
    """Everything that goes into one index artifact."""

    handbook: tuple[HandbookPage, ...]
    chunks: tuple[GuideChunk, ...]
    videos: Mapping[str, VideoLink]
    source_doc_id: str
    guides_commit_sha: str
    pipeline_version: str
    redaction_version: str


@dataclass(frozen=True, slots=True)
class IndexMeta:
    """The meta table of an artifact."""

    schema_version: str
    build_id: str
    content_hash: str
    guides_commit_sha: str
    source_doc_id: str
    pipeline_version: str
    redaction_version: str
    created_at_utc: str


@dataclass(frozen=True, slots=True)
class SearchHit:
    """One ranked Guides search result; lower score is a better bm25 match."""

    chunk: GuideChunk
    score: float
    video: VideoLink | None


def video_link(link: VideoLink) -> str:
    """Compose the playable URL: base URL, plus `#t=<whole seconds>` when an offset is known."""
    if link.start_seconds is None:
        return link.video_url
    return f"{link.video_url}#t={int(link.start_seconds)}"


def slugify(text: str) -> str:
    """Lowercase ASCII slug: NFKD, no combining marks, other character runs become one hyphen."""
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    out: list[str] = []
    pending_hyphen = False
    for ch in stripped.lower():
        if ("a" <= ch <= "z") or ("0" <= ch <= "9"):
            if pending_hyphen and out:
                out.append("-")
            pending_hyphen = False
            out.append(ch)
        else:
            pending_hyphen = True
    return "".join(out)


def make_chunk_key(file: str, h2: str, h3: str | None, part_index: int, occurrence: int = 1) -> str:
    """Heading-based chunk key that survives line shifts; `~N` disambiguates repeated headings."""
    key = f"{file}#{slugify(h2)}/{slugify(h3 or '') or '_'}/{part_index}"
    if occurrence > 1:
        key += f"~{occurrence}"
    return key
