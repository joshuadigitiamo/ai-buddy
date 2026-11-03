"""Local-only check of a real Guides checkout (plan 01-08).

Skipped unless ``GUIDES_LOCAL_DIR`` names an existing directory, so CI and other machines
never need the private Guides repository. Assertions compare counts and booleans; the
redaction table prints rule names and integers only.
"""

from __future__ import annotations

import logging
import os
import re
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

import pytest
import yaml

from buddy_core.index_reader import open_index
from buddy_core.index_writer import build_index
from buddy_core.models import GuideChunk, IndexContent, VideoLink
from buddy_sync.chunker import PIPELINE_VERSION, heading_outline
from buddy_sync.guides import build_guide_chunks, select_guide_files
from buddy_sync.guides_index import check_guides_index
from buddy_sync.redaction import REDACTION_VERSION, Redactor
from buddy_sync.video_map import parse_readme_videos, resolve_video_links

_ENV = os.environ.get("GUIDES_LOCAL_DIR", "")
GUIDES_DIR = Path(_ENV) if _ENV else None

pytestmark = pytest.mark.skipif(
    GUIDES_DIR is None or not GUIDES_DIR.is_dir(),
    reason="local-only: GUIDES_LOCAL_DIR does not name a Guides checkout",
)

MCP_GUIDE = "AI-Engineering/MCP_SERVERS_GUIDE.md"
MULTI_GUIDE = "AI-Engineering/MULTI_AGENT_ARCHITECTURE_DESIGN.md"
_HIT_LINE = re.compile(r"rule=(\w+) count=(\d+)")


def _root() -> Path:
    assert GUIDES_DIR is not None
    return GUIDES_DIR


class _HitCollector(logging.Handler):
    """Sums the per-rule counts of the redaction INFO records."""

    def __init__(self) -> None:
        super().__init__(level=logging.INFO)
        self.totals: Counter[str] = Counter()

    def emit(self, record: logging.LogRecord) -> None:
        match = _HIT_LINE.search(record.getMessage())
        if match:
            self.totals[match.group(1)] += int(match.group(2))


@pytest.fixture(scope="module")
def files() -> list[str]:
    return select_guide_files(_root())


@pytest.fixture(scope="module")
def built(files: list[str]) -> tuple[list[GuideChunk], Counter[str]]:
    logger = logging.getLogger("test_guides_local.build")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    collector = _HitCollector()
    logger.addHandler(collector)
    try:
        redactor = Redactor(email_allow_domains=frozenset({"digitiamo.com"}))
        chunks = build_guide_chunks(_root(), files, redactor=redactor, logger=logger)
    finally:
        logger.removeHandler(collector)
    return chunks, collector.totals


@pytest.fixture(scope="module")
def links(built: tuple[list[GuideChunk], Counter[str]]) -> dict[str, VideoLink]:
    chunks, _ = built
    return resolve_video_links(_root(), chunks, logger=logging.getLogger("test_guides_local.map"))


def test_selects_seventeen_guide_files(files: list[str]) -> None:
    assert len(files) == 17
    assert MCP_GUIDE in files
    assert MULTI_GUIDE in files


def test_builds_many_chunks(built: tuple[list[GuideChunk], Counter[str]]) -> None:
    chunks, _ = built
    assert len(chunks) > 2000


def test_two_mapped_guides_have_scene_links(
    built: tuple[list[GuideChunk], Counter[str]], links: dict[str, VideoLink]
) -> None:
    chunks, _ = built
    for guide in (MCP_GUIDE, MULTI_GUIDE):
        scene_chunks = [
            c for c in chunks if c.file == guide and links[c.chunk_key].source == "scene"
        ]
        assert len(scene_chunks) >= 5


def test_every_video_guide_chunk_has_a_link_and_dash_rows_have_none(
    built: tuple[list[GuideChunk], Counter[str]], links: dict[str, VideoLink]
) -> None:
    chunks, _ = built
    readme = parse_readme_videos((_root() / "README.md").read_text(encoding="utf-8"))
    with_video = [c for c in chunks if c.file in readme]
    without_video = [c for c in chunks if c.file not in readme]
    assert with_video
    assert without_video
    assert all(c.chunk_key in links for c in with_video)
    assert not any(c.chunk_key in links for c in without_video)


def test_guides_index_has_no_drift(files: list[str]) -> None:
    outline = {rel: heading_outline((_root() / rel).read_text(encoding="utf-8")) for rel in files}
    drifts = check_guides_index(
        _root(), outline, strict=True, logger=logging.getLogger("test_guides_local.index")
    )
    assert drifts == []


def test_search_finds_scene_linked_chunk_of_mcp_guide(
    built: tuple[list[GuideChunk], Counter[str]], links: dict[str, VideoLink], tmp_path: Path
) -> None:
    chunks, _ = built
    sections = yaml.safe_load(
        (_root() / "videos" / "mcp-servers" / "sections.yaml").read_text(encoding="utf-8")
    )
    first_heading = str(sections["sections"][0]["h2"])
    query = re.sub(r"^\d+\.\s*", "", first_heading)
    content = IndexContent(
        handbook=(),
        chunks=tuple(chunks),
        videos=links,
        source_doc_id="local-guides-check",
        guides_commit_sha="local",
        pipeline_version=PIPELINE_VERSION,
        redaction_version=REDACTION_VERSION,
    )
    dest = tmp_path / "index.db"
    build_index(content, dest, now=datetime.now(UTC))
    with open_index(dest) as reader:
        hits = reader.search_guides(query, limit=20)
    assert any(
        hit.chunk.file == MCP_GUIDE and hit.video is not None and hit.video.source == "scene"
        for hit in hits
    )


def test_redaction_hit_counts_over_the_guides(
    built: tuple[list[GuideChunk], Counter[str]],
) -> None:
    """D-18 false-positive check: prints rule names and integers only, asserts nothing secret."""
    _, totals = built
    print("\nredaction hits over the Guides (rule: count)")
    for rule, count in sorted(totals.items()):
        print(f"  {rule}: {count}")
    assert all(count >= 0 for count in totals.values())
