"""No log line carries the text of a question (MCP-05, D-10)."""

import logging

import pytest
from fastmcp import Client, FastMCP

pytestmark = pytest.mark.anyio


async def test_no_log_line_contains_a_query_or_question(
    server: FastMCP, caplog: pytest.LogCaptureFixture
) -> None:
    # The fastmcp logger does not propagate to the root logger: attach the capture handler.
    fastmcp_logger = logging.getLogger("fastmcp")
    fastmcp_logger.addHandler(caplog.handler)
    caplog.set_level(logging.INFO, logger="fastmcp")
    try:
        with caplog.at_level(logging.INFO):
            async with Client(server) as client:
                await client.call_tool("handbook_search", {"query": "sentinella-q-1823"})
                await client.call_tool("guides_search", {"query": "sentinella-q-1823"})
                await client.call_tool(
                    "buddy_report_gap", {"question": "sentinella-d-1823 domanda?"}
                )
                await client.read_resource("handbook://02-ferie")
    finally:
        fastmcp_logger.removeHandler(caplog.handler)
    assert "sentinella-" not in caplog.text
    assert all("sentinella-" not in record.getMessage() for record in caplog.records)


def test_capture_wiring_sees_fastmcp_records(caplog: pytest.LogCaptureFixture) -> None:
    """Guards the hygiene test above against passing because nothing was captured."""
    fastmcp_logger = logging.getLogger("fastmcp")
    fastmcp_logger.addHandler(caplog.handler)
    try:
        caplog.set_level(logging.INFO, logger="fastmcp")
        logging.getLogger("fastmcp.server").info("probe-line")
    finally:
        fastmcp_logger.removeHandler(caplog.handler)
    assert "probe-line" in caplog.text
