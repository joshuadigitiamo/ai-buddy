"""buddy_report_gap: record a question the sources could not answer (MCP-05, D-10).

The tool never reads the access token or the request context: a gap carries the
question, the queries tried and a timestamp, and nothing that identifies the asker.
"""

import logging
from collections.abc import Callable
from datetime import datetime

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.tools import ToolResult
from mcp.types import ToolAnnotations

from buddy_mcp.gaplog import GapLog, GapRecord, GapRecordError
from buddy_mcp.models import GAP_MARKER, GapReportOutput

logger = logging.getLogger(__name__)

# The one tool that is not read-only; it only appends, so it is never destructive.
GAP_ANNOTATIONS = ToolAnnotations(
    read_only_hint=False,
    destructive_hint=False,
    idempotent_hint=False,
    open_world_hint=False,
)

_DESCRIPTION = (
    "Record a question that the handbook and the Guides could not answer: call it when a search "
    "returned status no_results, or when no returned source supports an answer. It stores only "
    "the question, the queries tried and a timestamp, never who asked. Call it once, after "
    "replying 'non lo so, chiedi a ...'."
)

_RECORDED_TEXT = "Domanda registrata come lacuna (nessuna fonte trovata)."


def register_gap_tool(
    mcp: FastMCP,
    *,
    gaplog: GapLog,
    build_id: str,
    ttl_days: int,
    now: Callable[[], datetime],
) -> None:
    """Register buddy_report_gap on `mcp`, writing through the GapLog port."""

    @mcp.tool(
        name="buddy_report_gap",
        description=_DESCRIPTION,
        annotations=GAP_ANNOTATIONS,
        output_schema=GapReportOutput.model_json_schema(),
    )
    async def buddy_report_gap(question: str, tried: list[str] | None = None) -> ToolResult:
        try:
            gap = GapRecord.new(
                question, build_id=build_id, now=now(), ttl_days=ttl_days, tried=tried or ()
            )
        except GapRecordError as exc:
            # The message names the broken rule, never the question text.
            raise ToolError(str(exc)) from None
        try:
            gap_id = await gaplog.record(gap)
        except Exception as exc:
            # Only the exception type is logged: its message could carry the question.
            logger.warning("gap log write failed: %s", type(exc).__name__)
            raise ToolError("gap log unavailable") from None
        out = GapReportOutput(status="recorded", gap_id=gap_id, marker=GAP_MARKER)
        return ToolResult(content=_RECORDED_TEXT, structured_content=out.model_dump(mode="json"))
