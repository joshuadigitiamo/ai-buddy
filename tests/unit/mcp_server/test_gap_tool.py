"""buddy_report_gap: records an unanswered question without any caller identity (MCP-05, D-10)."""

import dataclasses
import logging
from collections.abc import Callable
from datetime import timedelta
from typing import Any

import pytest
from fastmcp import Client, FastMCP
from pydantic import ValidationError
from tests.unit.mcp_server.conftest import NOW, WEB_BASE

from buddy_mcp.config import McpSettings
from buddy_mcp.gaplog import GapRecord, InMemoryGapLog
from buddy_mcp.snapshot import IndexSnapshot

pytestmark = pytest.mark.anyio

QUESTION = "Posso portare il cane in ufficio?"


async def _report(
    server: FastMCP, question: str, tried: list[str] | None = None
) -> tuple[dict[str, Any] | None, str, bool]:
    arguments: dict[str, Any] = {"question": question}
    if tried is not None:
        arguments["tried"] = tried
    async with Client(server) as client:
        result = await client.call_tool("buddy_report_gap", arguments, raise_on_error=False)
    text = "".join(getattr(block, "text", "") for block in result.content)
    return result.structured_content, text, result.is_error


class _FailingGapLog:
    async def record(self, gap: GapRecord) -> str:
        raise RuntimeError("backend down")


async def test_report_records_one_gap_and_returns_the_marker(
    make_server: Callable[..., FastMCP], gaplog: InMemoryGapLog, snapshot: IndexSnapshot
) -> None:
    server = make_server()
    out, text, is_error = await _report(
        server, f"  {QUESTION}  ", ["handbook_search: cane ufficio"]
    )
    assert is_error is False
    assert out == {"status": "recorded", "gap_id": "memory-1", "marker": "nessuna fonte trovata"}
    assert "nessuna fonte trovata" in text
    assert len(gaplog.records) == 1
    gap = gaplog.records[0]
    assert gap.question == QUESTION
    assert gap.created_at == NOW
    assert gap.expire_at == NOW + timedelta(days=90)
    assert gap.build_id == snapshot.meta.build_id
    assert gap.tried == ("handbook_search: cane ufficio",)


async def test_report_without_tried_records_an_empty_tuple(
    server: FastMCP, gaplog: InMemoryGapLog
) -> None:
    _, _, is_error = await _report(server, QUESTION)
    assert is_error is False
    assert gaplog.records[0].tried == ()


async def test_ttl_follows_the_settings(
    index_dir: Any,
    snapshot: IndexSnapshot,
    gaplog: InMemoryGapLog,
    make_server: Callable[..., FastMCP],
) -> None:
    from buddy_mcp.server import build_server

    config = McpSettings(artifact_dir=index_dir, guides_web_base=WEB_BASE, gap_ttl_days=7)
    server = build_server(config, snapshot=snapshot, gaplog=gaplog, now=lambda: NOW)
    await _report(server, QUESTION)
    assert gaplog.records[0].expire_at == NOW + timedelta(days=7)


@pytest.mark.parametrize("question", ["", "   ", "x" * 2001])
async def test_invalid_question_is_an_error_that_does_not_echo_it(
    server: FastMCP, gaplog: InMemoryGapLog, question: str
) -> None:
    _, text, is_error = await _report(server, question)
    assert is_error is True
    assert text
    if question.strip():
        assert question not in text
    assert gaplog.records == []


async def test_backend_failure_is_gap_log_unavailable_and_logs_the_type_only(
    make_server: Callable[..., FastMCP], caplog: pytest.LogCaptureFixture
) -> None:
    server = make_server(gaplog=_FailingGapLog())
    with caplog.at_level(logging.INFO):
        _, text, is_error = await _report(server, "domanda-segreta-77?")
    assert is_error is True
    assert "gap log unavailable" in text
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert "RuntimeError" in warnings[0].getMessage()
    assert "domanda-segreta-77" not in caplog.text
    assert "backend down" not in caplog.text


def test_gap_ttl_days_must_be_at_least_one(index_dir: Any) -> None:
    with pytest.raises(ValidationError, match="gap_ttl_days"):
        McpSettings(artifact_dir=index_dir, guides_web_base=WEB_BASE, gap_ttl_days=0)


def test_gap_ttl_days_from_the_environment(index_dir: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ARTIFACT_DIR", str(index_dir))
    monkeypatch.setenv("GUIDES_WEB_BASE", WEB_BASE)
    monkeypatch.setenv("GAP_TTL_DAYS", "0")
    with pytest.raises(ValidationError, match="gap_ttl_days"):
        McpSettings()
    monkeypatch.setenv("GAP_TTL_DAYS", "30")
    assert McpSettings().gap_ttl_days == 30


def test_gap_settings_defaults(index_dir: Any) -> None:
    config = McpSettings(artifact_dir=index_dir, guides_web_base=WEB_BASE)
    assert config.gap_ttl_days == 90
    assert config.gap_collection == "gaps"


@pytest.mark.parametrize("collection", ["gaps/../x", "", "a b", "gaps/sub"])
def test_gap_collection_is_restricted(index_dir: Any, collection: str) -> None:
    with pytest.raises(ValidationError, match="gap_collection"):
        McpSettings(artifact_dir=index_dir, guides_web_base=WEB_BASE, gap_collection=collection)


def test_gap_record_has_no_identity_field() -> None:
    names = {field.name for field in dataclasses.fields(GapRecord)}
    assert names == {"question", "created_at", "expire_at", "build_id", "tried"}
