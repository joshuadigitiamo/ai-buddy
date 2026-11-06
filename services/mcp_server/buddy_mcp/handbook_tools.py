"""handbook_search: Italian keyword search over whole handbook pages (MCP-02, D-01..D-04)."""

from fastmcp import FastMCP
from fastmcp.tools import ToolResult

from buddy_core.models import HandbookPage
from buddy_mcp.guides_tools import READ_ONLY
from buddy_mcp.models import (
    DEFAULT_LIMIT,
    HandbookPageResult,
    HandbookSearchOutput,
    clamp_limit,
)
from buddy_mcp.snapshot import IndexSnapshot

_SEARCH_DESCRIPTION = (
    "Search the Italian company handbook with Italian keywords. Returns whole pages with "
    "source_url (handbook://...) and revision_date. status no_results means the handbook has "
    "no answer: do not answer from memory, call buddy_report_gap. Use handbook_get() for the "
    "table of contents."
)


def page_uri(page_id: str) -> str:
    """Citation URI of a handbook page (D-04: no web URL exists for the local snapshot)."""
    return f"handbook://{page_id}"


def page_result(page: HandbookPage) -> HandbookPageResult:
    """One whole page (D-03) with its citation and last-updated date."""
    return HandbookPageResult(
        page_id=page.page_id,
        title=page.title,
        text=page.content_md,
        source_url=page_uri(page.page_id),
        revision_date=page.revision_date_iso or "",
        revision_kind="last_updated",
    )


def render_page(item: HandbookPageResult) -> str:
    """Italian rendering of one page for the text content block."""
    return "\n".join(
        [
            f"# {item.title}",
            item.text,
            f"Fonte: {item.source_url}",
            f"Revisione: {item.revision_date[:10]}",
        ]
    )


def register_handbook_tools(mcp: FastMCP, snapshot: IndexSnapshot) -> None:
    """Register the handbook tools on `mcp`; all read from the cold-start snapshot."""

    @mcp.tool(
        name="handbook_search",
        description=_SEARCH_DESCRIPTION,
        annotations=READ_ONLY,
        output_schema=HandbookSearchOutput.model_json_schema(),
    )
    async def handbook_search(query: str, limit: int = DEFAULT_LIMIT) -> ToolResult:
        hits = snapshot.handbook_index.search(query, clamp_limit(limit))
        results = [page_result(page) for page in hits]
        out = HandbookSearchOutput(
            status="ok" if results else "no_results", query=query, results=results
        )
        text = (
            "\n\n".join(render_page(item) for item in results)
            if results
            else f"Nessun risultato per: {query}"
        )
        return ToolResult(content=text, structured_content=out.model_dump(mode="json"))
