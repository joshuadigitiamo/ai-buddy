"""Collect phase over the real bot workflow, then the score hand-off (amended D-20).

The bot is reused through its ports (D-13): `run_workflow` over a real MCP connector, with an
empty history (D-06). The LLM client and the connector are built inside the coroutine, once per
item, so no async client outlives its event loop. Logs carry item ids and statuses only.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import Any, Final, Literal

from buddy_bot.mcp_client import McpToolError
from buddy_bot.ports import LlmClient, LlmError, McpConnector
from buddy_bot.schemas import BotReply
from buddy_bot.workflow import WorkflowConfig, WorkflowDeps, run_workflow
from buddy_eval.config import EvalSettings
from buddy_eval.golden import GoldenItem
from buddy_eval.scoring import ItemVerdict, score_item
from buddy_eval.tracing import TraceSink

LOGGER: Final = logging.getLogger("buddy_eval")
TRACE_NAME: Final = "bot_run"
RUN_NAME: Final = "eval-run"
STOP_MESSAGE: Final = "stopped after {n} consecutive errors; re-run the same command to resume"

LlmFactory = Callable[[], LlmClient]
ConnectorFactory = Callable[[str], McpConnector]
Sleep = Callable[[float], Awaitable[None]]


@dataclass(frozen=True, slots=True)
class ItemOutcome:
    """What the bot did for one item; `error` is an exception type name, never a message."""

    item_id: str
    status: Literal["completed", "errored"]
    reply: BotReply | None
    trace_id: str | None
    error: str | None


@dataclass(frozen=True, slots=True)
class RunResult:
    """Outcomes and verdicts in id order; `aborted` is set by the consecutive-error stop."""

    outcomes: tuple[ItemOutcome, ...]
    verdicts: tuple[ItemVerdict, ...]
    aborted: bool


def _errored(item: GoldenItem, error: str, trace_id: str | None = None) -> ItemOutcome:
    return ItemOutcome(item.id, "errored", None, trace_id, error)


async def collect_item(
    item: GoldenItem,
    *,
    config: WorkflowConfig,
    llm_factory: LlmFactory,
    connector_factory: ConnectorFactory,
    mcp_url: str,
    sink: TraceSink,
) -> ItemOutcome:
    """Run one item through the bot under one trace and log its expectations on that trace."""

    async def fn() -> dict[str, Any]:
        deps = WorkflowDeps(llm_factory(), connector_factory(mcp_url), config)
        reply = await run_workflow(item.question, [], deps)
        return reply.model_dump(mode="json")

    try:
        output, trace_id = await sink.traced(
            TRACE_NAME, {"item_id": item.id, "kind": item.kind}, fn
        )
    except (LlmError, McpToolError) as exc:
        return _errored(item, type(exc).__name__)
    sink.log_expectations(
        trace_id,
        {
            "expected_sources": list(item.expected_sources),
            "key_facts": list(item.key_facts),
            "expected_referente_role": item.expected_referente_role,
            "kind": item.kind,
        },
    )
    reply = BotReply.model_validate(output)
    if reply.kind == "error":
        return _errored(item, "ErrorReply", trace_id)
    return ItemOutcome(item.id, "completed", reply, trace_id, None)


async def run_items(
    items: Sequence[GoldenItem],
    *,
    settings: EvalSettings,
    llm_factory: LlmFactory,
    connector_factory: ConnectorFactory,
    sink: TraceSink,
    sleep: Sleep = asyncio.sleep,
) -> RunResult:
    """Collect every item in id order inside one sink run, then hand the verdicts to the sink."""
    config = WorkflowConfig(
        reformulate_model=settings.reformulate_model,
        answer_model=settings.answer_model,
        confidence_threshold=settings.confidence_threshold,
    )
    ordered = sorted(items, key=lambda item: item.id)
    outcomes: list[ItemOutcome] = []
    consecutive_errors = 0
    aborted = False
    with sink.run(RUN_NAME, {"items": str(len(ordered))}):
        for index, item in enumerate(ordered):
            if index > 0 and settings.item_pause_seconds > 0:
                # The MCP server rate limit counts every request (RESEARCH Pitfall 7).
                await sleep(settings.item_pause_seconds)
            outcome = await collect_item(
                item,
                config=config,
                llm_factory=llm_factory,
                connector_factory=connector_factory,
                mcp_url=settings.mcp_url,
                sink=sink,
            )
            LOGGER.info("item %s %s", item.id, outcome.status)
            outcomes.append(outcome)
            # A completed item resets the run of errors; an errored one is never retried (D-14).
            consecutive_errors = consecutive_errors + 1 if outcome.status == "errored" else 0
            if consecutive_errors >= settings.max_consecutive_errors:
                LOGGER.warning("run stopped after %d consecutive errors", consecutive_errors)
                aborted = True
                break
        # Items after an abort were never collected: they get no outcome and no verdict.
        verdicts = tuple(
            score_item(item, outcome) for item, outcome in zip(ordered, outcomes, strict=False)
        )
        scored = {
            v.trace_id: v for v in verdicts if v.trace_id is not None and v.status != "errored"
        }
        sink.score(list(scored), scored)
    return RunResult(tuple(outcomes), verdicts, aborted=aborted)
