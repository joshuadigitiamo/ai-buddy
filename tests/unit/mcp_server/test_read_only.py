"""No tool or resource read changes the index or the artifact directory (MCP-07 read-only)."""

import hashlib
from pathlib import Path

import pytest
from fastmcp import Client, FastMCP

pytestmark = pytest.mark.anyio


def _fingerprint(directory: Path) -> tuple[str, list[str]]:
    digest = hashlib.sha256((directory / "index.db").read_bytes()).hexdigest()
    return digest, sorted(entry.name for entry in directory.iterdir())


async def test_calling_every_tool_leaves_the_index_untouched(
    server: FastMCP, index_dir: Path
) -> None:
    before = _fingerprint(index_dir)
    async with Client(server) as client:
        await client.call_tool("handbook_get", {})
        await client.call_tool("handbook_get", {"section": "02-ferie"})
        await client.call_tool("handbook_get", {"section": "nope"}, raise_on_error=False)
        await client.call_tool("handbook_search", {"query": "ferie"})
        await client.call_tool("handbook_search", {"query": "zzzz-nothing"})
        await client.call_tool("guides_search", {"query": "chunking"})
        await client.call_tool("guides_search", {"query": "zzzz-nothing"})
        await client.call_tool("guides_get_section", {"id": "nope"})
        await client.call_tool("buddy_report_gap", {"question": "Quando chiude la sede?"})
        await client.read_resource("handbook://02-ferie")
    assert _fingerprint(index_dir) == before
