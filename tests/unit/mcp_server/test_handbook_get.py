"""handbook_get: table of contents and exact page lookup (D-07, D-08)."""

from typing import Any

import pytest
from fastmcp import Client, FastMCP

pytestmark = pytest.mark.anyio


async def _call(server: FastMCP, tool: str, **arguments: Any) -> tuple[dict[str, Any], str, bool]:
    async with Client(server) as client:
        result = await client.call_tool(tool, arguments, raise_on_error=False)
    text = "".join(getattr(block, "text", "") for block in result.content)
    assert result.structured_content is not None
    return result.structured_content, text, result.is_error


async def test_no_section_returns_the_table_of_contents_in_position_order(
    server: FastMCP,
) -> None:
    out, text, is_error = await _call(server, "handbook_get")
    assert is_error is False
    assert (out["status"], out["query"], out["results"]) == ("ok", None, [])
    assert [entry["page_id"] for entry in out["toc"]] == [
        "01-benvenuto",
        "02-ferie",
        "03-malattia",
        "04-sede",
    ]
    assert out["toc"][1] == {
        "page_id": "02-ferie",
        "title": "Ferie e permessi",
        "source_url": "handbook://02-ferie",
        "revision_date": "2026-10-03T00:00:00+00:00",
        "revision_kind": "last_updated",
    }
    assert "02-ferie - Ferie e permessi (revisione 2026-10-03)" in text.splitlines()


async def test_section_returns_the_page_as_search_does(server: FastMCP) -> None:
    out, text, _ = await _call(server, "handbook_get", section="02-ferie")
    searched, _, _ = await _call(server, "handbook_search", query="ferie")
    assert (out["status"], out["toc"]) == ("ok", [])
    assert out["results"] == [searched["results"][0]]
    assert text.startswith("# Ferie e permessi\n")
    assert "Fonte: handbook://02-ferie" in text


@pytest.mark.parametrize("section", ["ferie", "../02-ferie", "", "02-FERIE", "02-ferie/"])
async def test_unknown_or_path_like_section_is_no_results(server: FastMCP, section: str) -> None:
    out, text, is_error = await _call(server, "handbook_get", section=section)
    assert (out["status"], out["results"], out["toc"], is_error) == ("no_results", [], [], False)
    assert text == f"Nessun risultato per: {section}"
