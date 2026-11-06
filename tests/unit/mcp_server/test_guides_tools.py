"""guides_search and guides_get_section through the in-memory FastMCP client."""

from collections.abc import Callable
from typing import Any

import pytest
from fastmcp import Client, FastMCP
from tests.unit.mcp_server.conftest import (
    MAPPED,
    PLAIN,
    SHA,
    SINGLE,
    WEB_BASE,
    make_chunk,
    make_content,
)

from buddy_core.models import GuideChunk, IndexContent
from buddy_mcp.guides_tools import guides_permalink

pytestmark = pytest.mark.anyio

_CITATION_FIELDS = ("source_url", "revision_date", "revision_kind", "video_url")


async def _call(server: FastMCP, tool: str, **arguments: Any) -> tuple[dict[str, Any], str, bool]:
    async with Client(server) as client:
        result = await client.call_tool(tool, arguments, raise_on_error=False)
    text = "".join(getattr(block, "text", "") for block in result.content)
    assert result.structured_content is not None
    return result.structured_content, text, result.is_error


@pytest.mark.parametrize("query", ["", "   ", "?!", "zzzz-nothing"])
async def test_unanswerable_query_is_no_results_not_an_error(server: FastMCP, query: str) -> None:
    out, text, is_error = await _call(server, "guides_search", query=query)
    assert (out["status"], out["results"], out["query"], is_error) == (
        "no_results",
        [],
        query,
        False,
    )
    assert text == f"Nessun risultato per: {query}"


async def test_search_operators_are_matched_as_plain_words(server: FastMCP) -> None:
    out, _, is_error = await _call(
        server, "guides_search", query='chunking OR NEAR(x) title:* "\x00'
    )
    assert is_error is False
    assert out["status"] == "ok"
    assert out["results"][0]["section_id"] == MAPPED.chunk_key


def _many_matches(count: int) -> IndexContent:
    chunks = tuple(
        make_chunk(f"Topic {i}", None, i * 10, i * 10 + 3, "retrieval pipeline note")
        for i in range(1, count + 1)
    )
    return make_content(chunks=chunks, videos={})


@pytest.mark.parametrize(("limit", "expected"), [(0, 1), (-3, 1), (10, 10), (11, 10), (50, 10)])
async def test_limit_is_clamped(
    server_for: Callable[[IndexContent], FastMCP], limit: int, expected: int
) -> None:
    out, _, _ = await _call(
        server_for(_many_matches(12)), "guides_search", query="retrieval", limit=limit
    )
    assert len(out["results"]) == expected


async def test_limit_defaults_to_five(server_for: Callable[[IndexContent], FastMCP]) -> None:
    out, _, _ = await _call(server_for(_many_matches(12)), "guides_search", query="retrieval")
    assert len(out["results"]) == 5


async def test_identical_chunks_come_back_in_index_order(
    server_for: Callable[[IndexContent], FastMCP],
) -> None:
    first = make_chunk("Alpha", None, 1, 3, "shared words here")
    second = make_chunk("Bravo", None, 5, 7, "shared words here")
    server = server_for(make_content(chunks=(first, second), videos={}))
    one, _, _ = await _call(server, "guides_search", query="shared")
    two, _, _ = await _call(server, "guides_search", query="shared")
    assert [r["section_id"] for r in one["results"]] == [first.chunk_key, second.chunk_key]
    assert one["results"] == two["results"]


async def test_get_section_returns_the_same_citation_as_search(server: FastMCP) -> None:
    found, _, _ = await _call(server, "guides_search", query="chunking")
    got, text, is_error = await _call(server, "guides_get_section", id=MAPPED.chunk_key)
    assert is_error is False
    assert got["status"] == "ok"
    assert len(got["results"]) == 1
    for field in _CITATION_FIELDS:
        assert got["results"][0][field] == found["results"][0][field]
    assert got["results"][0]["video_url"] == "https://videos.example.invalid/demo.mp4#t=12"
    assert got["results"][0]["source_url"] in text


async def test_get_section_unknown_id_is_no_results(server: FastMCP) -> None:
    out, text, is_error = await _call(server, "guides_get_section", id="Nope.md#x/_/0")
    assert (out["status"], out["results"], is_error) == ("no_results", [], False)
    assert text.startswith("Nessun risultato")


async def test_unmapped_section_has_no_video(server: FastMCP) -> None:
    out, _, _ = await _call(server, "guides_get_section", id=PLAIN.chunk_key)
    assert out["results"][0]["video_url"] is None


async def test_single_line_section_uses_a_single_line_anchor(server: FastMCP) -> None:
    out, _, _ = await _call(server, "guides_search", query="embedding")
    assert out["results"][0]["source_url"].endswith("DEMO_GUIDE.md#L40")


def test_permalink_pins_commit_and_range_anchor() -> None:
    assert guides_permalink(WEB_BASE, SHA, MAPPED) == (
        f"{WEB_BASE}/blob/{SHA}/AI-Engineering/DEMO_GUIDE.md#L10-L14"
    )


def test_permalink_single_line_anchor() -> None:
    assert guides_permalink(WEB_BASE, SHA, SINGLE).endswith("#L40")


def test_permalink_percent_encodes_spaces_in_the_path() -> None:
    chunk: GuideChunk = make_chunk("H", None, 3, 6, "t", file="Foundations/My Guide.md")
    assert "Foundations/My%20Guide.md#L3-L6" in guides_permalink(WEB_BASE, SHA, chunk)
