"""search_guides: hostile input never raises; stemming; stable tie order; limit clamp."""

from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest

from buddy_core.index_reader import IndexReader, open_index, to_match_query
from buddy_core.index_writer import build_index
from buddy_core.models import GuideChunk, IndexContent, make_chunk_key

NOW = datetime(2026, 11, 3, 10, 0, 0, tzinfo=UTC)

HOSTILE = [
    '"',
    "what: is-this?",
    "-",
    "*",
    '""unbalanced',
    "   \t\n ",
    "",
    "è perché",
    "NOT AND OR",
    "create_agent",
    "heading:chunking",
    "chunk*",
    "(chunking",
    "a\x00b",
    "NEAR(a b)",
    "'; DROP TABLE guide_chunks; --",
]


def _chunk(h2: str, h3: str | None, line_start: int, text: str) -> GuideChunk:
    file = "Demo/DEMO_GUIDE.md"
    return GuideChunk(
        chunk_key=make_chunk_key(file, h2, h3, 0),
        file=file,
        h2=h2,
        h3=h3,
        heading=h3 or h2,
        line_start=line_start,
        line_end=line_start + 4,
        part_index=0,
        text=text,
    )


def _open(content: IndexContent, tmp_path: Path) -> IndexReader:
    dest = tmp_path / "index.db"
    build_index(content, dest, now=NOW)
    return open_index(dest)


@pytest.mark.parametrize("query", HOSTILE)
def test_hostile_input_never_raises(
    sample_content: IndexContent, tmp_path: Path, query: str
) -> None:
    with _open(sample_content, tmp_path) as reader:
        assert isinstance(reader.search_guides(query), list)


@pytest.mark.parametrize("query", ['"', "-", "*", "   \t\n ", "", "?! ..."])
def test_punctuation_and_whitespace_only_return_empty(
    sample_content: IndexContent, tmp_path: Path, query: str
) -> None:
    assert to_match_query(query) is None
    with _open(sample_content, tmp_path) as reader:
        assert reader.search_guides(query) == []


def test_injection_text_leaves_the_data_intact(
    sample_content: IndexContent, tmp_path: Path
) -> None:
    with _open(sample_content, tmp_path) as reader:
        reader.search_guides("'; DROP TABLE guide_chunks; --")
        assert len(reader.guide_chunks()) == 2


def test_porter_stemming_matches_inflected_form(
    sample_content: IndexContent, tmp_path: Path
) -> None:
    with _open(sample_content, tmp_path) as reader:
        hits = reader.search_guides("chunks")
    assert [h.chunk.heading for h in hits] == ["Chunking"]
    assert hits[0].video is not None


def test_underscore_identifier_is_matchable(sample_content: IndexContent, tmp_path: Path) -> None:
    extra = _chunk("Agents", "Factory", 50, "Call create_agent to build one.")
    content = replace(sample_content, chunks=(*sample_content.chunks, extra))
    with _open(content, tmp_path) as reader:
        hits = reader.search_guides("create_agent")
    assert [h.chunk.heading for h in hits] == ["Factory"]


def test_diacritics_are_folded(sample_content: IndexContent, tmp_path: Path) -> None:
    extra = _chunk("Cafe", None, 60, "A caffè example.")
    content = replace(sample_content, chunks=(*sample_content.chunks, extra))
    with _open(content, tmp_path) as reader:
        hits = reader.search_guides("caffe")
    assert [h.chunk.heading for h in hits] == ["Cafe"]


def test_equal_scores_are_ordered_by_chunk_id(sample_content: IndexContent, tmp_path: Path) -> None:
    # Same text, same heading words: identical bm25 score. Ids follow (file, line_start).
    first = _chunk("Twin", "A", 100, "zebra crossing rules")
    second = _chunk("Twin", "A", 200, "zebra crossing rules")
    second = replace(second, chunk_key=second.chunk_key + "~2")
    content = replace(sample_content, chunks=(second, first, *sample_content.chunks))
    with _open(content, tmp_path) as reader:
        hits = reader.search_guides("zebra")
    assert [h.chunk.line_start for h in hits] == [100, 200]
    assert hits[0].score == hits[1].score


def test_limit_is_clamped(sample_content: IndexContent, tmp_path: Path) -> None:
    chunks = tuple(
        replace(
            _chunk("Many", f"H{i}", 100 + i * 10, "shared keyword"),
            chunk_key=f"k{i}",
        )
        for i in range(60)
    )
    content = replace(sample_content, chunks=chunks, videos={})
    with _open(content, tmp_path) as reader:
        assert len(reader.search_guides("shared", limit=1)) == 1
        assert len(reader.search_guides("shared", limit=0)) == 1
        assert len(reader.search_guides("shared", limit=-5)) == 1
        assert len(reader.search_guides("shared", limit=10_000)) == 50


def test_heading_match_outranks_body_match(sample_content: IndexContent, tmp_path: Path) -> None:
    in_heading = _chunk("Quokka", None, 100, "unrelated words here")
    in_body = _chunk("Other", None, 200, "a quokka appears in this body text")
    content = replace(sample_content, chunks=(in_body, in_heading), videos={})
    with _open(content, tmp_path) as reader:
        hits = reader.search_guides("quokka")
    assert [h.chunk.h2 for h in hits] == ["Quokka", "Other"]
