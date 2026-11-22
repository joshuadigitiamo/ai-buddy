"""Reachability checks before the first live run (meridian_opus resolution, RESEARCH OQ 1).

One tiny structured call per configured model (reformulate, answer, judge), one MCP session and
one connection to the MLflow server. A successful Opus call is the only evidence that the judge
model works inside the Max plan: the tier mapping is not visible to the client (RESEARCH A2).
Output is limited to check names, model ids, host names and exception type names; no key, no URL
credentials and no prompt text (T-05-35).
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from typing import Final
from urllib.parse import urlsplit

from pydantic import BaseModel

from buddy_bot.ports import LlmClient, McpConnector
from buddy_eval.config import EvalSettings
from buddy_eval.tracing import TraceSink

PING_SYSTEM: Final = "Rispondi con ok true."
PING_USER: Final = "ping"
PING_MAX_TOKENS: Final = 50
UNSET: Final = "(unset)"

LlmFactory = Callable[[], LlmClient]
ConnectorFactory = Callable[[str], McpConnector]
SinkFactory = Callable[[EvalSettings], TraceSink]


class PreflightPing(BaseModel):
    """The reply the ping asks for; any reply that parses proves the model answers."""

    ok: bool


@dataclass(frozen=True, slots=True)
class PreflightCheck:
    """One check; `error` is an exception type name, never a message."""

    check: str
    target: str
    ok: bool
    error: str | None = None

    def render(self) -> str:
        outcome = "ok" if self.ok else f"failed ({self.error})"
        return f"preflight {self.check} {self.target}: {outcome}"


def _safe_url(url: str | None) -> str:
    """Scheme, host, port and path only: credentials and query strings never print."""
    if not url:
        return UNSET
    parts = urlsplit(url)
    host = parts.hostname or ""
    port = f":{parts.port}" if parts.port else ""
    return f"{parts.scheme}://{host}{port}{parts.path}"


def _result(check: str, target: str, error: Exception | None) -> PreflightCheck:
    return PreflightCheck(
        check, target, error is None, None if error is None else type(error).__name__
    )


async def _ping(llm_factory: LlmFactory, check: str, model: str) -> PreflightCheck:
    try:
        # A fresh client per call, so one failed model cannot poison the next check.
        await llm_factory().structured(
            PreflightPing,
            model=model,
            system=PING_SYSTEM,
            user=PING_USER,
            max_tokens=PING_MAX_TOKENS,
        )
    except Exception as exc:  # any failure is a reported check result, never a crash
        return _result(check, model, exc)
    return _result(check, model, None)


async def _open_session(connector_factory: ConnectorFactory, url: str) -> PreflightCheck:
    target = _safe_url(url)
    try:
        async with connector_factory(url).session():
            pass
    except Exception as exc:  # any failure is a reported check result, never a crash
        return _result("mcp", target, exc)
    return _result("mcp", target, None)


async def _model_and_mcp_checks(
    settings: EvalSettings, llm_factory: LlmFactory, connector_factory: ConnectorFactory
) -> list[PreflightCheck]:
    checks = [
        await _ping(llm_factory, "reformulate", settings.reformulate_model),
        await _ping(llm_factory, "answer", settings.answer_model),
        await _ping(llm_factory, "judge", settings.judge_model),
    ]
    checks.append(await _open_session(connector_factory, settings.mcp_url))
    return checks


def run_preflight(
    *,
    settings: EvalSettings,
    llm_factory: LlmFactory,
    connector_factory: ConnectorFactory,
    sink_factory: SinkFactory,
) -> list[PreflightCheck]:
    """The five checks in the order reformulate, answer, judge, mcp, mlflow."""
    checks = asyncio.run(_model_and_mcp_checks(settings, llm_factory, connector_factory))
    target = _safe_url(settings.mlflow_tracking_uri)
    try:
        # The constructor contacts the tracking server through set_experiment.
        sink_factory(settings)
    except Exception as exc:  # any failure is a reported check result, never a crash
        checks.append(_result("mlflow", target, exc))
    else:
        checks.append(_result("mlflow", target, None))
    return checks
