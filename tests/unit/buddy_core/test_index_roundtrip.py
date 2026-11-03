"""Tracer: a handbook page and a Guides chunk survive build, publish, open, read and search."""

from datetime import UTC, datetime
from pathlib import Path

from buddy_core.index_reader import open_index
from buddy_core.index_writer import build_index
from buddy_core.models import (
    GuideChunk,
    HandbookPage,
    IndexContent,
    VideoLink,
    make_chunk_key,
    video_link,
)
from buddy_core.store import LocalDirArtifactStore

NOW = datetime(2026, 11, 3, 10, 0, 0, tzinfo=UTC)
VIDEO = VideoLink("https://videos.example.invalid/demo.mp4", 1, 312.4, "scene")


def _page(page_id: str, parent: str | None, position: int, depth: int, title: str) -> HandbookPage:
    return HandbookPage(
        page_id=page_id,
        parent_id=parent,
        position=position,
        depth=depth,
        title=title,
        url=f"https://docs.example.invalid/w/v/dc/d/{page_id}",
        date_edited_raw=1_700_000_000_000 + position,
        date_created_raw=1_690_000_000_000,
        revision_date_iso="2023-11-14",
        content_md=f"# {title}\n\nSynthetic body {page_id}.",
        content_hash=f"hash-{page_id}",
    )


def _chunk(h2: str, h3: str | None, line_start: int, text: str) -> GuideChunk:
    file = "Demo/DEMO_GUIDE.md"
    return GuideChunk(
        chunk_key=make_chunk_key(file, h2, h3, 0),
        file=file,
        h2=h2,
        h3=h3,
        heading=h3 or h2,
        line_start=line_start,
        line_end=line_start + 9,
        part_index=0,
        text=text,
    )


def make_content() -> IndexContent:
    mapped = _chunk("2. Retrieval", "Chunking", 40, "Chunking splits documents at headings.")
    unmapped = _chunk("3. Serving", None, 80, "Deploy the service behind a gateway.")
    return IndexContent(
        handbook=(
            _page("p-root", None, 0, 0, "Root page"),
            _page("p-child", "p-root", 1, 1, "Child page"),
        ),
        chunks=(mapped, unmapped),
        videos={mapped.chunk_key: VIDEO},
        source_doc_id="doc-synthetic",
        guides_commit_sha="0" * 40,
        pipeline_version="test-1",
        redaction_version="test-1",
    )


def test_page_and_chunk_roundtrip_through_published_artifact(tmp_path: Path) -> None:
    store = LocalDirArtifactStore(tmp_path / "artifacts")
    content = make_content()
    staged = store.staging_path()
    meta = build_index(content, staged, now=NOW)
    published = store.publish(staged, meta)

    assert store.latest_path() == published
    with open_index(published) as reader:
        assert reader.meta == meta
        pages = reader.load_handbook()
        assert [p.page_id for p in pages] == ["p-root", "p-child"]
        assert [(p.url, p.title, p.revision_date_iso) for p in pages] == [
            (p.url, p.title, p.revision_date_iso) for p in content.handbook
        ]
        assert reader.get_page("p-child") == content.handbook[1]
        assert reader.get_page("missing") is None
        assert set(reader.guide_chunks()) == set(content.chunks)
        assert reader.video_links() == content.videos

        hits = reader.search_guides("chunking")
        assert len(hits) == 1
        first = hits[0]
        assert first.chunk.file == "Demo/DEMO_GUIDE.md"
        assert (first.chunk.line_start, first.chunk.line_end) == (40, 49)
        assert first.video is not None
        assert video_link(first.video).endswith("#t=312")

        other = reader.search_guides("gateway")
        assert [h.chunk.heading for h in other] == ["3. Serving"]
        assert other[0].video is None


def test_video_link_without_offset_is_the_bare_url() -> None:
    link = VideoLink("https://videos.example.invalid/demo.mp4", 2, None, "readme_fallback")
    assert video_link(link) == "https://videos.example.invalid/demo.mp4"
