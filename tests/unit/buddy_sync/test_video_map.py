"""Video map: tracer through the index, then multi-part, fallbacks and contract breaks."""

import logging
from datetime import UTC, datetime
from pathlib import Path

from buddy_core.index_reader import open_index
from buddy_core.index_writer import build_index
from buddy_core.models import GuideChunk, IndexContent, make_chunk_key, video_link
from buddy_core.store import LocalDirArtifactStore
from buddy_sync.video_map import resolve_video_links

FIXTURE_ROOT = Path(__file__).resolve().parents[2] / "fixtures" / "guides_videos"
DEMO = "AI-Engineering/DEMO_GUIDE.md"
LOGGER = logging.getLogger("buddy_sync.test")


def make_chunk(
    file: str, h2: str, h3: str | None, line_start: int, text: str = "Synthetic text."
) -> GuideChunk:
    return GuideChunk(
        chunk_key=make_chunk_key(file, h2, h3, 0),
        file=file,
        h2=h2,
        h3=h3,
        heading=h3 or h2,
        line_start=line_start,
        line_end=line_start + 3,
        part_index=0,
        text=text,
    )


def demo_chunks() -> list[GuideChunk]:
    return [
        make_chunk(DEMO, "1. Basics", None, 5, "Preamble about the watermark."),
        make_chunk(DEMO, "1. Basics", "Chunking", 9, "Chunking splits text by heading."),
        make_chunk(DEMO, "2. Only Section", None, 20, "A single paragraph."),
    ]


def test_mapped_section_has_timestamped_link(tmp_path: Path) -> None:
    chunks = demo_chunks()
    links = resolve_video_links(FIXTURE_ROOT, chunks, logger=LOGGER)
    content = IndexContent(
        handbook=(),
        chunks=tuple(chunks),
        videos=links,
        source_doc_id="doc-synthetic",
        guides_commit_sha="1" * 40,
        pipeline_version="test-1",
        redaction_version="test-1",
    )
    store = LocalDirArtifactStore(tmp_path / "artifacts")
    staged = store.staging_path()
    meta = build_index(content, staged, now=datetime.now(UTC))
    reader = open_index(store.publish(staged, meta))

    hits = {h.chunk.chunk_key: h for h in reader.search_guides("chunking")}
    chunking = hits[chunks[1].chunk_key]
    assert chunking.video is not None
    assert video_link(chunking.video) == "https://videos.example.invalid/demo.mp4#t=30"

    watermark = {h.chunk.chunk_key: h for h in reader.search_guides("watermark")}
    preamble = watermark[chunks[0].chunk_key]
    assert preamble.video is not None
    assert video_link(preamble.video).endswith("#t=10")

    only = {h.chunk.chunk_key: h for h in reader.search_guides("paragraph")}[chunks[2].chunk_key]
    assert only.video is not None
    assert only.video.source == "readme_fallback"
    assert "#t=" not in video_link(only.video)
