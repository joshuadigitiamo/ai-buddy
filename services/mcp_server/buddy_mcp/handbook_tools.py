"""Handbook tools and resource: search, table of contents, page lookup (MCP-02, MCP-06)."""

from fastmcp import FastMCP
from fastmcp.exceptions import ResourceError
from fastmcp.tools import ToolResult

from buddy_core.models import HandbookPage
from buddy_mcp.guides_tools import READ_ONLY
from buddy_mcp.models import (
    DEFAULT_LIMIT,
    HandbookGetOutput,
    HandbookPageResult,
    HandbookSearchOutput,
    HandbookTocEntry,
    clamp_limit,
)
from buddy_mcp.snapshot import IndexSnapshot

_SEARCH_DESCRIPTION = (
    "Search the Italian company handbook with Italian keywords. Returns whole pages with "
    "source_url (handbook://...) and revision_date. status no_results means the handbook has "
    "no answer: do not answer from memory, call buddy_report_gap. Use handbook_get() for the "
    "table of contents."
)

_GET_DESCRIPTION = (
    "With no section, return the table of contents (page_id, title, revision_date) of the "
    "handbook. With section = a page_id, return that whole page with source_url and "
    "revision_date. status no_results means the page_id is unknown."
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


def render_resource(page: HandbookPage) -> str:
    """Resource body: citation header, blank line, title, then the page markdown (MCP-06)."""
    revision = (page.revision_date_iso or "")[:10]
    header = f"Fonte: handbook://{page.page_id} - Revisione: {revision}"
    return f"{header}\n\n# {page.title}\n{page.content_md}"


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

    @mcp.tool(
        name="handbook_get",
        description=_GET_DESCRIPTION,
        annotations=READ_ONLY,
        output_schema=HandbookGetOutput.model_json_schema(),
    )
    async def handbook_get(section: str | None = None) -> ToolResult:
        if section is None:
            toc = [
                HandbookTocEntry(
                    page_id=page.page_id,
                    title=page.title,
                    source_url=page_uri(page.page_id),
                    revision_date=page.revision_date_iso or "",
                    revision_kind="last_updated",
                )
                for page in snapshot.pages.values()
            ]
            out = HandbookGetOutput(status="ok", query=None, results=[], toc=toc)
            text = "\n".join(
                f"{entry.page_id} - {entry.title} (revisione {entry.revision_date[:10]})"
                for entry in toc
            )
            return ToolResult(content=text, structured_content=out.model_dump(mode="json"))
        # Exact page_id only (D-07, D-08): the argument is never turned into a path.
        page = snapshot.pages.get(section)
        results = [page_result(page)] if page else []
        out = HandbookGetOutput(
            status="ok" if results else "no_results", query=section, results=results, toc=[]
        )
        text = render_page(results[0]) if results else f"Nessun risultato per: {section}"
        return ToolResult(content=text, structured_content=out.model_dump(mode="json"))

    @mcp.resource("handbook://{pagina}", mime_type="text/markdown")
    async def handbook_page(pagina: str) -> str:
        page = snapshot.pages.get(pagina)
        if page is None:
            raise ResourceError(f"Pagina non trovata: {pagina}")
        return render_resource(page)
