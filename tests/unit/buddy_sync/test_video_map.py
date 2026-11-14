"""Video map: tracer through the index, then multi-part, fallbacks and contract breaks."""

import logging
import shutil
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import pytest

from buddy_core.index_reader import open_index
from buddy_core.index_writer import build_index
from buddy_core.models import GuideChunk, IndexContent, VideoLink, make_chunk_key, video_link
from buddy_core.store import LocalDirArtifactStore
from buddy_sync.video_map import (
    MAX_SECTIONS_BYTES,
    VideoMapError,
    gcs_video_url,
    resolve_video_links,
    scene_offsets,
)

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


MULTI = "AI-Engineering/MULTI_GUIDE.md"
FALLBACK = "AI-Engineering/FALLBACK_GUIDE.md"
NOVIDEO = "Foundations/NOVIDEO_GUIDE.md"
MULTI_URL = "https://videos.example.invalid/multi_part{part}.mp4"


def multi_chunks() -> list[GuideChunk]:
    return [
        make_chunk(MULTI, "Overview", None, 2),
        make_chunk(MULTI, "1. Basics", None, 6),
        make_chunk(MULTI, "1. Basics", "Detail", 10),
        make_chunk(MULTI, "2. Recap", None, 20),
        make_chunk(MULTI, "2. Recap", "Deep", 24),
        make_chunk(MULTI, "2. Recap", "Other", 28),
        make_chunk(MULTI, "3. Appendix", None, 40),
    ]


def all_chunks() -> list[GuideChunk]:
    return [
        *demo_chunks(),
        *multi_chunks(),
        make_chunk(FALLBACK, "1. Intro", None, 3),
        make_chunk(FALLBACK, "1. Intro", "Part", 7),
        make_chunk(NOVIDEO, "1. Intro", None, 3),
    ]


def test_mapped_section_has_timestamped_link(tmp_path: Path) -> None:
    chunks = all_chunks()
    links = resolve()
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


# ---- Task 2: multi-part, fallbacks, contract breaks -------------------------------------------


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    root = tmp_path / "guides_videos"
    shutil.copytree(FIXTURE_ROOT, root)
    return root


def resolve(root: Path = FIXTURE_ROOT) -> dict[str, VideoLink]:
    """Resolve against the chunks of every fixture guide (each sections.yaml needs its guide)."""
    return resolve_video_links(root, all_chunks(), logger=LOGGER)


def by_key(links: dict[str, VideoLink], chunk: GuideChunk) -> VideoLink:
    return links[chunk.chunk_key]


def test_multi_part_offsets_restart_in_each_part() -> None:
    links = resolve()
    basics, recap, deep = (by_key(links, c) for c in (multi_chunks()[1], *multi_chunks()[3:5]))
    assert (basics.part, basics.start_seconds, basics.source) == (1, 15.0, "scene")
    assert basics.video_url == MULTI_URL.format(part=1)
    assert (recap.part, recap.start_seconds) == (2, 0.0)
    assert recap.video_url == MULTI_URL.format(part=2)
    assert (deep.part, deep.start_seconds) == (2, 12.0)


def test_h3_entry_beats_h2_only_entry_and_h2_covers_siblings() -> None:
    chunks = multi_chunks()
    links = resolve()
    assert by_key(links, chunks[4]).start_seconds == 12.0  # Deep: own h3 scene
    assert by_key(links, chunks[5]).start_seconds == 0.0  # Other: h2-only scene of its ##
    assert by_key(links, chunks[3]).start_seconds == 0.0  # preamble: h2-only scene
    assert by_key(links, chunks[2]).start_seconds == 15.0  # Detail: h2-only scene of 1. Basics


def test_unmapped_chunk_takes_part_of_nearest_preceding_mapped_chunk() -> None:
    chunks = multi_chunks()
    links = resolve()
    appendix = by_key(links, chunks[6])
    assert (appendix.source, appendix.part, appendix.start_seconds) == ("readme_fallback", 2, None)
    assert appendix.video_url == MULTI_URL.format(part=2)


def test_unmapped_chunk_before_any_mapped_chunk_is_part_one() -> None:
    chunks = multi_chunks()
    overview = by_key(resolve(), chunks[0])
    assert (overview.source, overview.part, overview.start_seconds) == ("readme_fallback", 1, None)


def test_guide_with_video_but_no_map_uses_readme_fallback() -> None:
    chunks = [c for c in all_chunks() if c.file == FALLBACK]
    links = resolve()
    assert all(c.chunk_key in links for c in chunks)
    for link in (links[c.chunk_key] for c in chunks):
        assert link == VideoLink(
            "https://videos.example.invalid/fallback.mp4", 1, None, "readme_fallback"
        )


def test_unmapped_section_after_a_mapped_one_keeps_the_fallback_and_does_not_inherit() -> None:
    """D-18, 04-01 coverage_inheritance (a): no offset is borrowed from the section before."""
    links = resolve()
    chunks = multi_chunks()
    mapped, appendix = by_key(links, chunks[5]), by_key(links, chunks[6])  # Other, then Appendix
    assert (mapped.source, mapped.part, mapped.start_seconds) == ("scene", 2, 0.0)
    assert (appendix.source, appendix.part, appendix.start_seconds) == ("readme_fallback", 2, None)
    assert appendix.video_url == mapped.video_url
    assert "#t=" not in video_link(appendix)
    only = by_key(links, demo_chunks()[2])  # follows the mapped Basics sections of the same part
    assert (only.source, only.start_seconds) == ("readme_fallback", None)
    assert "#t=" not in video_link(only)


def test_only_scene_links_carry_an_offset_and_no_inherited_source_exists() -> None:
    links = resolve()
    assert {link.source for link in links.values()} == {"scene", "readme_fallback"}
    for link in links.values():
        assert (link.start_seconds is not None) == (link.source == "scene")


def test_guide_without_video_gets_no_entry() -> None:
    chunks = all_chunks()
    links = resolve()
    assert not any(c.chunk_key in links for c in chunks if c.file == NOVIDEO)
    assert len(links) == len(chunks) - 1


def test_duplicate_target_keeps_first_and_warns(
    tree: Path, caplog: pytest.LogCaptureFixture
) -> None:
    path = tree / "videos" / "demo" / "sections.yaml"
    path.write_text(
        path.read_text() + '  - scene: S01Title\n    h2: "1. Basics"\n    h3: Chunking\n'
    )
    chunks = demo_chunks()
    with caplog.at_level(logging.WARNING, logger=LOGGER.name):
        links = resolve(tree)
    assert by_key(links, chunks[1]).start_seconds == 30.5  # S03Chunking, listed first
    assert any("duplicate target" in r.getMessage() for r in caplog.records)


def test_empty_sections_list_makes_every_chunk_a_fallback(tree: Path) -> None:
    path = tree / "videos" / "demo" / "sections.yaml"
    path.write_text("schema: 1\nguide: AI-Engineering/DEMO_GUIDE.md\nvideo: demo\nsections: []\n")
    chunks = demo_chunks()
    links = resolve(tree)
    assert [links[c.chunk_key].source for c in chunks] == ["readme_fallback"] * 3
    assert all(links[c.chunk_key].start_seconds is None for c in chunks)


def test_reordering_durations_changes_offsets(tree: Path) -> None:
    durations = tree / "videos" / "demo" / "out" / "durations.json"
    durations.write_text('{"S03Chunking": 30.0, "S01Title": 10.0, "S02Intro": 20.5}')
    chunks = demo_chunks()
    links = resolve(tree)
    assert by_key(links, chunks[1]).start_seconds == 0.0
    assert by_key(links, chunks[0]).start_seconds == 40.0


def test_scene_offsets_follow_key_order_and_part_prefix() -> None:
    assert scene_offsets(
        {"S01A": 1.5, "S02B": 2.0, "P2S01C": 4.0, "P2S02D": 1.0, "P1S01E": 3.0}
    ) == {
        "S01A": (1, 0.0),
        "S02B": (1, 1.5),
        "P2S01C": (2, 0.0),
        "P2S02D": (2, 4.0),
        "P1S01E": (1, 3.5),
    }


def _edit(rel: str, old: str, new: str, *, count: int = -1) -> Callable[[Path], None]:
    def apply(root: Path) -> None:
        path = root / rel
        text = path.read_text()
        assert old in text, f"fixture drifted: {old!r} not in {rel}"
        path.write_text(text.replace(old, new, count))

    return apply


def _write(rel: str, content: str) -> Callable[[Path], None]:
    def apply(root: Path) -> None:
        (root / rel).write_text(content)

    return apply


def _unlink(rel: str) -> Callable[[Path], None]:
    def apply(root: Path) -> None:
        (root / rel).unlink()

    return apply


def _second_file_for_same_guide(root: Path) -> None:
    shutil.copytree(root / "videos" / "demo", root / "videos" / "demo2")
    _edit("videos/demo2/sections.yaml", "video: demo", "video: demo2")(root)


DEMO_YAML = "videos/demo/sections.yaml"
DEMO_JSON = "videos/demo/out/durations.json"

BREAKS: dict[str, tuple[Callable[[Path], None], str]] = {
    "unknown_scene": (_edit(DEMO_YAML, "S02Intro", "S99Missing"), "S99Missing"),
    "h2_without_chunk": (_edit(DEMO_YAML, '"1. Basics"', '"9. Ghost"'), "9. Ghost"),
    "h3_without_chunk": (_edit(DEMO_YAML, "h3: Chunking", "h3: Ghost"), "Ghost"),
    "guide_dotdot": (_edit(DEMO_YAML, "AI-Engineering/DEMO_GUIDE.md", "../outside.md"), "guide"),
    "guide_absolute": (_edit(DEMO_YAML, "AI-Engineering/DEMO_GUIDE.md", "/abs/path.md"), "guide"),
    "guide_backslash": (
        _edit(
            DEMO_YAML,
            "guide: AI-Engineering/DEMO_GUIDE.md",
            "guide: 'AI-Engineering\\DEMO_GUIDE.md'",
        ),
        "guide",
    ),
    "guide_not_indexed": (
        _edit(DEMO_YAML, "AI-Engineering/DEMO_GUIDE.md", "AI-Engineering/OTHER_GUIDE.md"),
        "OTHER_GUIDE",
    ),
    "guide_without_readme_video": (
        _edit(DEMO_YAML, "AI-Engineering/DEMO_GUIDE.md", NOVIDEO),
        "no video in README",
    ),
    "video_slug_differs": (_edit(DEMO_YAML, "video: demo", "video: other"), "video"),
    "part_missing_from_readme": (
        lambda root: (
            _edit("videos/multi/sections.yaml", "P2S02Deep", "P3S02Deep")(root),
            _edit("videos/multi/out/durations.json", "P2S02Deep", "P3S02Deep")(root),
        )[0],
        "part 3",
    ),
    "durations_missing": (_unlink(DEMO_JSON), "durations.json"),
    "durations_is_a_list": (_write(DEMO_JSON, "[1, 2, 3]"), "durations.json"),
    "durations_not_json": (_write(DEMO_JSON, "{not json"), "durations.json"),
    "durations_value_not_number": (_write(DEMO_JSON, '{"S02Intro": "ten"}'), "S02Intro"),
    "unknown_key": (_edit(DEMO_YAML, "video: demo", "video: demo\nextra: 1"), "extra"),
    "schema_version_2": (_edit(DEMO_YAML, "schema: 1", "schema: 2"), "schema"),
    "python_object_tag": (
        _write(DEMO_YAML, "guide: !!python/object/apply:os.getcwd []\nvideo: demo\n"),
        "sections.yaml",
    ),
    "oversize": (_write(DEMO_YAML, "# " + "x" * MAX_SECTIONS_BYTES + "\n"), "larger than"),
    "same_guide_mapped_twice": (_second_file_for_same_guide, "two files"),
    "readme_absent": (_unlink("README.md"), "README.md"),
}


@pytest.mark.parametrize("name", list(BREAKS))
def test_contract_break_fails_loudly_and_names_the_file(tree: Path, name: str) -> None:
    mutate, expected = BREAKS[name]
    mutate(tree)
    with pytest.raises(VideoMapError) as caught:
        resolve_video_links(tree, all_chunks(), logger=LOGGER)
    message = str(caught.value)
    assert expected in message
    assert "sections.yaml" in message or "durations.json" in message or "README.md" in message
    assert "os.getcwd" not in message


def test_missing_readme_without_any_map_returns_nothing(tmp_path: Path) -> None:
    assert resolve_video_links(tmp_path, all_chunks(), logger=LOGGER) == {}


# ---- hosted video URLs (url_for) --------------------------------------------------------------


def test_url_for_rewrite_leaves_no_query_string_and_keeps_the_scene_offset() -> None:
    links = resolve_video_links(
        FIXTURE_ROOT, all_chunks(), logger=LOGGER, url_for=gcs_video_url("demo-ai-buddy-videos")
    )
    assert links
    for link in links.values():
        assert "?" not in link.video_url
        assert link.video_url.startswith("https://storage.cloud.google.com/demo-ai-buddy-videos/")
    chunking = links[demo_chunks()[1].chunk_key]
    assert video_link(chunking).endswith("/videos/demo.mp4#t=30")


def test_url_for_with_two_readme_urls_sharing_a_basename_is_a_map_error(tree: Path) -> None:
    readme = tree / "README.md"
    readme.write_text(
        readme.read_text()
        .replace("multi_part2.mp4", "multi_part1.mp4")
        .replace(
            "https://videos.example.invalid/multi_part1.mp4)<br>",
            "https://other.example.invalid/multi_part1.mp4)<br>",
            1,
        )
    )
    # Without a rewrite the README keeps working (the clash only matters for object names).
    resolve_video_links(tree, all_chunks(), logger=LOGGER)
    with pytest.raises(VideoMapError, match="share the name"):
        resolve_video_links(tree, all_chunks(), logger=LOGGER, url_for=gcs_video_url("b-bucket"))
