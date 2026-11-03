"""Shared synthetic content for the buddy_core contract tests (no real ids or handbook text)."""

import pytest

from buddy_core.models import (
    GuideChunk,
    HandbookPage,
    IndexContent,
    VideoLink,
    make_chunk_key,
)

FILE = "Demo/DEMO_GUIDE.md"


def _make_page(page_id: str, position: int, content_md: str = "Synthetic body.") -> HandbookPage:
    return HandbookPage(
        page_id=page_id,
        parent_id=None,
        position=position,
        depth=0,
        title=f"Page {page_id}",
        url=f"https://docs.example.invalid/w/v/dc/d/{page_id}",
        date_edited_raw=1_700_000_000_000,
        date_created_raw=1_690_000_000_000,
        revision_date_iso="2023-11-14",
        content_md=content_md,
        content_hash=f"hash-{page_id}",
    )


def _make_guide_chunk(h2: str, h3: str | None, line_start: int, text: str) -> GuideChunk:
    return GuideChunk(
        chunk_key=make_chunk_key(FILE, h2, h3, 0),
        file=FILE,
        h2=h2,
        h3=h3,
        heading=h3 or h2,
        line_start=line_start,
        line_end=line_start + 4,
        part_index=0,
        text=text,
    )


@pytest.fixture
def sample_content() -> IndexContent:
    mapped = _make_guide_chunk("Retrieval", "Chunking", 10, "Chunking splits documents.")
    plain = _make_guide_chunk("Serving", None, 30, "Deploy behind a gateway.")
    return IndexContent(
        handbook=(_make_page("p-a", 0), _make_page("p-b", 1)),
        chunks=(mapped, plain),
        videos={mapped.chunk_key: VideoLink("https://v.example.invalid/x.mp4", 1, 12.0, "scene")},
        source_doc_id="doc-synthetic",
        guides_commit_sha="1" * 40,
        pipeline_version="test-1",
        redaction_version="test-1",
    )
