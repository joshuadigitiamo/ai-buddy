"""guides_search: keyword search over the English Guides with citations (MCP-03, D-05)."""

from urllib.parse import quote

from fastmcp import FastMCP
from fastmcp.tools import ToolResult
from mcp.types import ToolAnnotations

from buddy_core.models import GuideChunk, VideoLink, video_link
from buddy_mcp.config import McpSettings
from buddy_mcp.models import (
    DEFAULT_LIMIT,
    GuidesGetSectionOutput,
    GuidesSearchOutput,
    GuidesSectionResult,
    clamp_limit,
)
from buddy_mcp.snapshot import IndexSnapshot

READ_ONLY = ToolAnnotations(
    read_only_hint=True,
    destructive_hint=False,
    idempotent_hint=True,
    open_world_hint=False,
)

_SEARCH_DESCRIPTION = (
    "Search the English Guides by keyword. Translate Italian terms to English keywords first. "
    "Each result carries source_url, revision_date (the index build date) and video_url when a "
    "video is mapped. status no_results means nothing matched: do not answer from memory, "
    "call buddy_report_gap. Fetch one section by its section_id with guides_get_section."
)

_GET_SECTION_DESCRIPTION = (
    "Return one Guides section by the section_id that guides_search returned, with source_url, "
    "revision_date (the index build date) and video_url. status no_results means the id is "
    "unknown."
)


def guides_permalink(web_base: str, commit_sha: str, chunk: GuideChunk) -> str:
    """GitHub permalink pinned to the indexed commit, with a line anchor (D-05)."""
    path = quote(chunk.file, safe="/")
    anchor = (
        f"L{chunk.line_start}"
        if chunk.line_start == chunk.line_end
        else f"L{chunk.line_start}-L{chunk.line_end}"
    )
    return f"{web_base}/blob/{commit_sha}/{path}#{anchor}"


def _result(
    snapshot: IndexSnapshot, settings: McpSettings, chunk: GuideChunk, video: VideoLink | None
) -> GuidesSectionResult:
    return GuidesSectionResult(
        section_id=chunk.chunk_key,
        file=chunk.file,
        heading=f"{chunk.h2} > {chunk.h3}" if chunk.h3 else chunk.h2,
        line_start=chunk.line_start,
        line_end=chunk.line_end,
        text=chunk.text,
        source_url=guides_permalink(
            settings.guides_web_base, snapshot.meta.guides_commit_sha, chunk
        ),
        revision_date=snapshot.meta.created_at_utc,
        revision_kind="indexed_on",
        video_url=video_link(video) if video else None,
    )


def _render_block(item: GuidesSectionResult) -> str:
    lines = [
        f"{item.heading} ({item.file}:L{item.line_start}-L{item.line_end})",
        item.text,
        f"Fonte: {item.source_url}",
        f"Indicizzato il: {item.revision_date[:10]}",
    ]
    if item.video_url:
        lines.append(f"Video: {item.video_url}")
    return "\n".join(lines)


def _render(results: list[GuidesSectionResult], empty: str) -> str:
    return "\n\n".join(_render_block(item) for item in results) if results else empty


def register_guides_tools(mcp: FastMCP, snapshot: IndexSnapshot, settings: McpSettings) -> None:
    """Register the Guides tools on `mcp`; all read from the cold-start snapshot."""

    # async def: sync tools run in a threadpool; the SQLite connection belongs to the loop thread.
    @mcp.tool(
        name="guides_search",
        description=_SEARCH_DESCRIPTION,
        annotations=READ_ONLY,
        output_schema=GuidesSearchOutput.model_json_schema(),
    )
    async def guides_search(query: str, limit: int = DEFAULT_LIMIT) -> ToolResult:
        hits = snapshot.reader.search_guides(query, clamp_limit(limit))
        results = [_result(snapshot, settings, hit.chunk, hit.video) for hit in hits]
        out = GuidesSearchOutput(
            status="ok" if results else "no_results", query=query, results=results
        )
        text = _render(results, f"Nessun risultato per: {query}")
        return ToolResult(content=text, structured_content=out.model_dump(mode="json"))

    @mcp.tool(
        name="guides_get_section",
        description=_GET_SECTION_DESCRIPTION,
        annotations=READ_ONLY,
        output_schema=GuidesGetSectionOutput.model_json_schema(),
    )
    async def guides_get_section(id: str) -> ToolResult:
        chunk = snapshot.chunks.get(id)
        results = (
            [_result(snapshot, settings, chunk, snapshot.videos.get(chunk.chunk_key))]
            if chunk
            else []
        )
        out = GuidesGetSectionOutput(
            status="ok" if results else "no_results", query=id, results=results
        )
        text = _render(results, f"Nessun risultato per: {id}")
        return ToolResult(content=text, structured_content=out.model_dump(mode="json"))
