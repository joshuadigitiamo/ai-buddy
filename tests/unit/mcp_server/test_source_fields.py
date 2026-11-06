"""No output without a source: every item and TOC entry is cited (MCP-03, ROADMAP criterion 2)."""

from datetime import datetime
from typing import Any

import pytest
from fastmcp import Client, FastMCP
from tests.unit.mcp_server.conftest import MAPPED, PLAIN, SHA, SINGLE, WEB_BASE

pytestmark = pytest.mark.anyio

PAGE_IDS = ("01-benvenuto", "02-ferie", "03-malattia", "04-sede")
GUIDES_PREFIX = f"{WEB_BASE}/blob/{SHA}/"
VIDEO_URL = "https://videos.example.invalid/demo.mp4#t=12"


def assert_cited(structured: dict[str, Any]) -> list[dict[str, Any]]:
    """Fail on any result or TOC item without a source_url and a parseable revision_date.

    Returns the checked items so callers can assert on them without walking twice.
    """
    items = [*structured.get("results", []), *structured.get("toc", [])]
    for item in items:
        assert item.get("source_url"), f"item without source_url: {item}"
        assert item.get("revision_date"), f"item without revision_date: {item}"
        datetime.fromisoformat(item["revision_date"])
        assert item.get("revision_kind") in {"last_updated", "indexed_on"}, item
    return items


def _is_handbook(item: dict[str, Any]) -> bool:
    return str(item["source_url"]).startswith("handbook://") and (
        item["revision_kind"] == "last_updated"
    )


def _is_guides(item: dict[str, Any]) -> bool:
    return str(item["source_url"]).startswith(GUIDES_PREFIX) and (
        item["revision_kind"] == "indexed_on"
    )


async def _call(server: FastMCP, tool: str, **arguments: Any) -> tuple[dict[str, Any], str]:
    async with Client(server) as client:
        result = await client.call_tool(tool, arguments)
    assert result.structured_content is not None
    text = "".join(getattr(block, "text", "") for block in result.content)
    return result.structured_content, text


def _assert_text_carries_every_source(items: list[dict[str, Any]], text: str) -> None:
    for item in items:
        assert item["source_url"] in text, f"text lacks {item['source_url']}"


def test_assert_cited_rejects_an_item_without_source_url() -> None:
    good = {
        "source_url": "handbook://x",
        "revision_date": "2026-10-03T00:00:00+00:00",
        "revision_kind": "last_updated",
    }
    assert assert_cited({"results": [good], "toc": []}) == [good]
    broken = {key: value for key, value in good.items() if key != "source_url"}
    with pytest.raises(AssertionError):
        assert_cited({"results": [broken]})
    with pytest.raises(AssertionError):
        assert_cited({"toc": [{**good, "revision_date": ""}]})


@pytest.mark.parametrize("query", ["ferie", "malattia", "benvenuto", "citta"])
async def test_handbook_search_results_are_cited(server: FastMCP, query: str) -> None:
    out, text = await _call(server, "handbook_search", query=query)
    items = assert_cited(out)
    assert items, f"fixture query {query} found nothing"
    assert all(_is_handbook(item) for item in items)
    _assert_text_carries_every_source(items, text)


async def test_handbook_toc_entries_are_cited(server: FastMCP) -> None:
    out, text = await _call(server, "handbook_get")
    items = assert_cited(out)
    assert [item["page_id"] for item in items] == list(PAGE_IDS)
    assert all(_is_handbook(item) for item in items)
    _assert_text_carries_every_source(items, text)


@pytest.mark.parametrize("page_id", PAGE_IDS)
async def test_handbook_get_page_is_cited(server: FastMCP, page_id: str) -> None:
    out, text = await _call(server, "handbook_get", section=page_id)
    items = assert_cited(out)
    assert [item["source_url"] for item in items] == [f"handbook://{page_id}"]
    assert _is_handbook(items[0])
    _assert_text_carries_every_source(items, text)


@pytest.mark.parametrize("query", ["chunking", "gateway", "embedding"])
async def test_guides_search_results_are_cited(server: FastMCP, query: str) -> None:
    out, text = await _call(server, "guides_search", query=query)
    items = assert_cited(out)
    assert items, f"fixture query {query} found nothing"
    assert all(_is_guides(item) for item in items)
    _assert_text_carries_every_source(items, text)


@pytest.mark.parametrize("chunk", [MAPPED, PLAIN, SINGLE], ids=["mapped", "plain", "single"])
async def test_guides_get_section_is_cited_with_the_right_video(
    server: FastMCP, chunk: Any
) -> None:
    out, text = await _call(server, "guides_get_section", id=chunk.chunk_key)
    items = assert_cited(out)
    assert len(items) == 1
    assert _is_guides(items[0])
    _assert_text_carries_every_source(items, text)
    expected_video = VIDEO_URL if chunk is MAPPED else None
    assert items[0]["video_url"] == expected_video
    if expected_video:
        assert expected_video in text


async def test_only_the_gap_tool_has_no_source_fields(server: FastMCP) -> None:
    async with Client(server) as client:
        tools = {tool.name: tool for tool in await client.list_tools()}
    without_items = []
    for name, tool in tools.items():
        assert tool.output_schema is not None
        if "results" not in tool.output_schema["properties"]:
            without_items.append(name)
            assert "source_url" not in str(tool.output_schema)
        else:
            assert "source_url" in str(tool.output_schema), name
    assert without_items == ["buddy_report_gap"]
