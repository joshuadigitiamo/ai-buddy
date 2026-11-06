"""Every content tool answers a miss the same way: explicit, empty, no filler (MCP-04, D-08)."""

from typing import Any

import pytest
from fastmcp import Client, FastMCP

pytestmark = pytest.mark.anyio

MISSES: list[tuple[str, dict[str, Any], str]] = [
    ("handbook_search", {"query": "zzzz-nothing"}, "zzzz-nothing"),
    ("guides_search", {"query": "zzzz-nothing"}, "zzzz-nothing"),
    ("handbook_get", {"section": "nope"}, "nope"),
    ("guides_get_section", {"id": "nope"}, "nope"),
]


@pytest.mark.parametrize(("tool", "arguments", "query"), MISSES, ids=[m[0] for m in MISSES])
async def test_a_miss_is_data_not_an_error(
    server: FastMCP, tool: str, arguments: dict[str, Any], query: str
) -> None:
    async with Client(server) as client:
        result = await client.call_tool(tool, arguments, raise_on_error=False)
    assert result.is_error is False
    out = result.structured_content
    assert out is not None
    assert out["status"] == "no_results"
    assert out["results"] == []
    assert out["query"] == query
    assert out.get("toc", []) == []
    text = "".join(getattr(block, "text", "") for block in result.content)
    assert text == f"Nessun risultato per: {query}"
