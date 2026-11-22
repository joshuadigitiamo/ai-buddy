"""Preflight: one ping per model, one MCP session and the MLflow connection; synthetic data only."""

import io
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastmcp import FastMCP
from tests.unit.buddy_eval.conftest import RecordingTraceSink
from tests.unit.chat_bot.conftest import FakeLlm

from buddy_bot.mcp_client import FastMcpConnector
from buddy_bot.ports import LlmUnavailableError, McpConnector, McpTools
from buddy_eval import cli
from buddy_eval.config import EvalSettings
from buddy_eval.preflight import PreflightPing, run_preflight
from buddy_eval.tracing import TracingError

PING = PreflightPing(ok=True)


class _Down:
    """A connector whose session cannot be opened."""

    @asynccontextmanager
    async def session(self) -> AsyncIterator[McpTools]:
        message = "connection refused secret-host-detail"
        raise ConnectionRefusedError(message)
        yield  # pragma: no cover


def _llm(*items: PreflightPing | Exception) -> FakeLlm:
    return FakeLlm({PreflightPing: list(items)})


def _main(
    settings: EvalSettings,
    llm: FakeLlm,
    *,
    connector: McpConnector | None = None,
    server: FastMCP | None = None,
    sink: Any = None,
) -> tuple[int, list[str]]:
    out = io.StringIO()

    def make_connector(_url: str) -> McpConnector:
        if connector is not None:
            return connector
        assert server is not None
        return FastMcpConnector(server)

    def make_sink(_settings: EvalSettings) -> Any:
        if isinstance(sink, Exception):
            raise sink
        return RecordingTraceSink()

    code = cli.main(
        ["preflight"],
        settings=settings,
        llm_factory=lambda: llm,
        connector_factory=make_connector,
        sink_factory=make_sink,
        out=out,
    )
    return code, out.getvalue().splitlines()


def test_all_checks_pass_prints_five_ok_lines_and_exits_0(
    eval_settings: EvalSettings, mcp_server: FastMCP
) -> None:
    llm = _llm(PING, PING, PING)

    code, lines = _main(eval_settings, llm, server=mcp_server)

    assert code == 0
    assert lines == [
        "preflight reformulate claude-haiku-5-5: ok",
        "preflight answer claude-sonnet-5-5: ok",
        "preflight judge claude-opus-5-5: ok",
        f"preflight mcp {eval_settings.mcp_url}: ok",
        "preflight mlflow (unset): ok",
    ]


def test_each_model_is_called_once_with_a_tiny_prompt(
    eval_settings: EvalSettings, mcp_server: FastMCP
) -> None:
    llm = _llm(PING, PING, PING)

    _main(eval_settings, llm, server=mcp_server)

    assert [(c.schema, c.model) for c in llm.calls] == [
        (PreflightPing, eval_settings.reformulate_model),
        (PreflightPing, eval_settings.answer_model),
        (PreflightPing, eval_settings.judge_model),
    ]
    assert {(c.system, c.user) for c in llm.calls} == {("Rispondi con ok true.", "ping")}


def test_an_unavailable_judge_model_fails_that_check_only(
    eval_settings: EvalSettings, mcp_server: FastMCP
) -> None:
    llm = _llm(PING, PING, LlmUnavailableError("unavailable secret-detail"))

    code, lines = _main(eval_settings, llm, server=mcp_server)

    assert code == 1
    assert "preflight judge claude-opus-5-5: failed (LlmUnavailableError)" in lines
    assert [line for line in lines if line.endswith(": ok")] == [
        "preflight reformulate claude-haiku-5-5: ok",
        "preflight answer claude-sonnet-5-5: ok",
        f"preflight mcp {eval_settings.mcp_url}: ok",
        "preflight mlflow (unset): ok",
    ]


def test_a_failing_mlflow_sink_fails_the_mlflow_line(
    eval_settings: EvalSettings, mcp_server: FastMCP
) -> None:
    llm = _llm(PING, PING, PING)

    code, lines = _main(eval_settings, llm, server=mcp_server, sink=TracingError("down"))

    assert code == 1
    assert lines[-1] == "preflight mlflow (unset): failed (TracingError)"


def test_an_unreachable_mcp_server_fails_the_mcp_line_without_its_message(
    eval_settings: EvalSettings,
) -> None:
    llm = _llm(PING, PING, PING)

    code, lines = _main(eval_settings, llm, connector=_Down())

    assert code == 1
    assert f"preflight mcp {eval_settings.mcp_url}: failed (ConnectionRefusedError)" in lines
    assert "secret-host-detail" not in "\n".join(lines)


def test_every_check_runs_even_when_all_fail(eval_settings: EvalSettings) -> None:
    llm = _llm(LlmUnavailableError("x"), LlmUnavailableError("x"), LlmUnavailableError("x"))

    code, lines = _main(eval_settings, llm, connector=_Down(), sink=TracingError("x"))

    assert code == 1
    assert len(lines) == 5
    assert all("failed (" in line for line in lines)


def test_urls_print_without_credentials_or_query(mcp_server: FastMCP) -> None:
    settings = EvalSettings(
        mcp_url="http://user:hunter2@mcp-server:8000/mcp?token=abc",
        mlflow_tracking_uri="http://user:hunter2@localhost:5000",
    )
    llm = _llm(PING, PING, PING)

    _, lines = _main(settings, llm, server=mcp_server)

    text = "\n".join(lines)
    assert "preflight mcp http://mcp-server:8000/mcp: ok" in lines
    assert "preflight mlflow http://localhost:5000: ok" in lines
    assert "hunter2" not in text
    assert "token" not in text


def test_run_preflight_returns_checks_in_order(
    eval_settings: EvalSettings, mcp_server: FastMCP
) -> None:
    llm = _llm(PING, PING, PING)

    checks = run_preflight(
        settings=eval_settings,
        llm_factory=lambda: llm,
        connector_factory=lambda _url: FastMcpConnector(mcp_server),
        sink_factory=lambda _s: RecordingTraceSink(),
    )

    assert [c.check for c in checks] == ["reformulate", "answer", "judge", "mcp", "mlflow"]
    assert all(c.ok and c.error is None for c in checks)


def test_a_client_is_built_fresh_for_each_ping(
    eval_settings: EvalSettings, mcp_server: FastMCP
) -> None:
    built: list[FakeLlm] = []

    def factory() -> FakeLlm:
        client = _llm(PING)
        built.append(client)
        return client

    run_preflight(
        settings=eval_settings,
        llm_factory=factory,
        connector_factory=lambda _url: FastMcpConnector(mcp_server),
        sink_factory=lambda _s: RecordingTraceSink(),
    )

    assert len(built) == 3
    assert [len(c.calls) for c in built] == [1, 1, 1]


def test_preflight_prints_no_prompt_text_or_key(
    eval_settings: EvalSettings, mcp_server: FastMCP
) -> None:
    settings = eval_settings.model_copy(update={"anthropic_api_key": None})
    llm = _llm(PING, PING, PING)

    _, lines = _main(settings, llm, server=mcp_server)

    text = "\n".join(lines)
    assert "Rispondi" not in text
    assert "ping" not in text.replace("preflight", "")
