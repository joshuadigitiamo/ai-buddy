"""handbook_search through the in-memory FastMCP client: Italian stems, edges, ordering."""

from collections.abc import Callable
from typing import Any

import pytest
from fastmcp import Client, FastMCP
from tests.unit.mcp_server.conftest import make_content, make_page

from buddy_core.models import IndexContent
from buddy_mcp.stemming import normalize, stem_query

pytestmark = pytest.mark.anyio

FERIE_TEXT = (
    "Come richiedere le ferie: invia la richiesta al responsabile con due settimane di anticipo."
)


async def _call(server: FastMCP, **arguments: Any) -> tuple[dict[str, Any], str, bool]:
    async with Client(server) as client:
        result = await client.call_tool("handbook_search", arguments, raise_on_error=False)
    text = "".join(getattr(block, "text", "") for block in result.content)
    assert result.structured_content is not None
    return result.structured_content, text, result.is_error


@pytest.mark.parametrize("query", ["quando posso chiedere una feria?", "richiedo ferie"])
async def test_italian_question_finds_the_whole_ferie_page_first(
    server: FastMCP, query: str
) -> None:
    out, text, is_error = await _call(server, query=query)
    assert is_error is False
    assert out["status"] == "ok"
    first = out["results"][0]
    assert first == {
        "page_id": "02-ferie",
        "title": "Ferie e permessi",
        "text": FERIE_TEXT,
        "source_url": "handbook://02-ferie",
        "revision_date": "2026-10-03T00:00:00+00:00",
        "revision_kind": "last_updated",
    }
    assert text.startswith("# Ferie e permessi\n")
    assert "Fonte: handbook://02-ferie\nRevisione: 2026-10-03" in text


@pytest.mark.parametrize("query", ["citta", "CITTÀ", "città"])
async def test_case_and_accents_fold_on_both_sides(server: FastMCP, query: str) -> None:
    out, _, _ = await _call(server, query=query)
    assert "04-sede" in [item["page_id"] for item in out["results"]]


@pytest.mark.parametrize("query", ["", "   ", "?!?", "come e quando", "zzzz-nothing"])
async def test_unanswerable_query_is_no_results_not_an_error(server: FastMCP, query: str) -> None:
    out, text, is_error = await _call(server, query=query)
    assert (out["status"], out["results"], out["query"], is_error) == (
        "no_results",
        [],
        query,
        False,
    )
    assert text == f"Nessun risultato per: {query}"


@pytest.mark.parametrize("query", ['ferie" OR title:* NEAR(', "ferie \x00 permessi", "*", '"'])
async def test_fts_operators_and_nul_are_inert(server: FastMCP, query: str) -> None:
    _, _, is_error = await _call(server, query=query)
    assert is_error is False


async def test_limit_is_clamped(server_for: Callable[[IndexContent], FastMCP]) -> None:
    pages = tuple(
        make_page(f"{i:02d}-nota", i, "Nota", "ferie aziendali", "2026-10-01T00:00:00+00:00")
        for i in range(8)
    )
    server = server_for(make_content(pages=pages))
    zero, _, _ = await _call(server, query="ferie", limit=0)
    default, _, _ = await _call(server, query="ferie")
    big, _, _ = await _call(server, query="ferie", limit=99)
    assert (len(zero["results"]), len(default["results"]), len(big["results"])) == (1, 5, 8)


async def test_identical_calls_return_identical_lists(server: FastMCP) -> None:
    first, _, _ = await _call(server, query="ferie città malattia")
    second, _, _ = await _call(server, query="ferie città malattia")
    assert first["results"] == second["results"]


async def test_equal_scores_keep_page_position_order(
    server_for: Callable[[IndexContent], FastMCP],
) -> None:
    pages = tuple(
        make_page(pid, pos, "Nota", "ferie aziendali", "2026-10-01T00:00:00+00:00")
        for pos, pid in enumerate(("10-prima", "20-seconda", "30-terza"))
    )
    out, _, _ = await _call(server_for(make_content(pages=pages)), query="ferie")
    assert [item["page_id"] for item in out["results"]] == ["10-prima", "20-seconda", "30-terza"]


def test_normalize_and_stem_query_fold_case_and_accents() -> None:
    assert normalize("CITTÀ Perché") == "citta perche"
    assert stem_query("Quando posso chiedere le ferie?") == stem_query("chiedere ferie")
