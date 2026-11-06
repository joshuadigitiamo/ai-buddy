"""The handbook://{pagina} resource template (MCP-06)."""

import pytest
from fastmcp import Client, FastMCP
from fastmcp.exceptions import McpError

pytestmark = pytest.mark.anyio


async def test_template_is_listed_and_no_static_resources(server: FastMCP) -> None:
    async with Client(server) as client:
        templates = await client.list_resource_templates()
        resources = await client.list_resources()
    assert [t.uriTemplate for t in templates] == ["handbook://{pagina}"]
    assert resources == []


async def test_reading_a_page_returns_citation_header_then_markdown(server: FastMCP) -> None:
    async with Client(server) as client:
        contents = await client.read_resource("handbook://02-ferie")
    assert len(contents) == 1
    text = getattr(contents[0], "text", "")
    assert text.splitlines()[:3] == [
        "Fonte: handbook://02-ferie - Revisione: 2026-10-03",
        "",
        "# Ferie e permessi",
    ]
    assert "Come richiedere le ferie" in text
    assert contents[0].mimeType == "text/markdown"


@pytest.mark.parametrize("uri", ["handbook://nope", "handbook://..%2F..%2Fetc%2Fpasswd"])
async def test_unknown_or_path_like_id_is_an_mcp_error(server: FastMCP, uri: str) -> None:
    async with Client(server) as client:
        with pytest.raises(McpError):
            await client.read_resource(uri)
