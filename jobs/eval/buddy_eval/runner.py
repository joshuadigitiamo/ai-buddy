"""Collect phase over the real bot workflow, the judge phase, then the score hand-off (D-20).

The bot is reused through its ports (D-13): `run_workflow` over a real MCP connector, with an
empty history (D-06). The LLM client and the connector are built inside the coroutine, once per
item, so no async client outlives its event loop. Logs carry item ids and statuses only.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final, Literal

from pydantic import ValidationError

from buddy_bot.mcp_client import McpToolError
from buddy_bot.ports import LlmClient, LlmError, McpConnector
from buddy_bot.schemas import BotReply
from buddy_bot.workflow import WorkflowConfig, WorkflowDeps, run_workflow
from buddy_eval.cache import ResultCache, bot_version, key_for
from buddy_eval.config import EvalSettings
from buddy_eval.golden import GoldenItem
from buddy_eval.judge import JUDGE_PROMPT_VERSION, JudgeVerdict, judge_reply
from buddy_eval.scoring import SCORING_VERSION, ItemVerdict, score_item
from buddy_eval.sources import IndexIdentity, SourceIndex
from buddy_eval.tracing import SCORER_SET_VERSION, TraceSink, TracingError

LOGGER: Final = logging.getLogger("buddy_eval")
TRACE_NAME: Final = "bot_run"
RUN_NAME: Final = "eval-run"
# Bump when ItemOutcome, BotReply or the cached payload change shape: it is a key ingredient, so
# older cached outcomes stop matching instead of failing to load.
OUTCOME_SCHEMA_VERSION: Final = 1
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
    """Outcomes and verdicts in id order; `aborted` is set by the consecutive-error stop.

    `identity` is the index the run was made against; it is None only for a run with no items,
    which opens no index.
    """

    outcomes: tuple[ItemOutcome, ...]
    verdicts: tuple[ItemVerdict, ...]
    aborted: bool
    identity: IndexIdentity | None = None


def scored_version(verdict: ItemVerdict) -> str:
    """The scored-marker version for one verdict: the scorer set plus a digest of the verdict.

    A trace is scored again when its verdict changes, and never twice for the same verdict.
    """
    digest = key_for(
        status=verdict.status,
        checks=dict(verdict.checks),
        reasons=list(verdict.reasons),
        invented=verdict.invented,
        judge=verdict.judge.model_dump(mode="json") if verdict.judge else None,
    )
    return f"{SCORER_SET_VERSION}-{digest[:16]}"


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
    except TracingError:
        raise
    except Exception as exc:  # noqa: BLE001 - a transport failure errors the item, never the run
        # Type name only: the message may carry a URL or request detail (T-05-53).
        LOGGER.warning("item %s errored: %s", item.id, type(exc).__name__)
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


def _outcome_payload(outcome: ItemOutcome) -> dict[str, object]:
    assert outcome.reply is not None
    return {
        "item_id": outcome.item_id,
        "trace_id": outcome.trace_id,
        "reply": outcome.reply.model_dump(mode="json"),
    }


def _outcome_from_payload(item: GoldenItem, payload: Mapping[str, Any]) -> ItemOutcome | None:
    """Rebuild a completed outcome from its cache payload; None when it does not fit."""
    trace_id = payload.get("trace_id")
    reply = payload.get("reply")
    if payload.get("item_id") != item.id or not isinstance(trace_id, str) or reply is None:
        return None
    try:
        return ItemOutcome(item.id, "completed", BotReply.model_validate(reply), trace_id, None)
    except ValidationError:
        return None


def _cached_outcome(
    cache: ResultCache, key: str, item: GoldenItem, sink: TraceSink
) -> ItemOutcome | None:
    """A cached outcome, only while its trace exists; otherwise the item is collected again."""
    payload = cache.get("outcome", key)
    if payload is None:
        return None
    outcome = _outcome_from_payload(item, payload)
    if outcome is None or outcome.trace_id is None or not sink.trace_exists(outcome.trace_id):
        return None
    return outcome


def _cached_verdict(cache: ResultCache, key: str) -> JudgeVerdict | None:
    """A cached judge verdict, or None for a missing or unusable file."""
    payload = cache.get("verdict", key)
    if payload is None:
        return None
    try:
        return JudgeVerdict.model_validate(payload)
    except ValidationError:
        return None


async def _judge_item(
    item: GoldenItem,
    outcome: ItemOutcome,
    *,
    outcome_key: str,
    settings: EvalSettings,
    llm_factory: LlmFactory,
    cache: ResultCache,
    sink: TraceSink,
) -> tuple[ItemOutcome, JudgeVerdict | None]:
    """The judge's verdict for one answered outcome, cached; a judge LlmError errors the item.

    A refusal, a referral or an error is never judged. A failed call is never cached, so a rerun
    asks the judge again while the cached outcome keeps its trace. The key holds a digest of the
    reply, so a verdict is reused only for the reply it judged (CR-01).
    """
    reply = outcome.reply
    if outcome.status != "completed" or reply is None or reply.kind != "answer":
        return outcome, None
    reply_digest = key_for(reply=reply.model_dump(mode="json"))
    key = key_for(
        outcome_key=outcome_key,
        reply_digest=reply_digest,
        judge_model=settings.judge_model,
        judge_prompt_version=JUDGE_PROMPT_VERSION,
        scoring_version=SCORING_VERSION,
    )
    verdict = _cached_verdict(cache, key)
    if verdict is not None:
        return outcome, verdict
    try:
        # The judge reads source text: its calls must not become traces (RESEARCH Pitfall 4).
        with sink.untraced():
            verdict = await judge_reply(llm_factory(), item, reply, model=settings.judge_model)
    except LlmError as exc:
        LOGGER.warning("item %s judge failed: %s", item.id, type(exc).__name__)
        return _errored(item, f"judge:{type(exc).__name__}", outcome.trace_id), None
    cache.put("verdict", key, verdict.model_dump(mode="json"))
    return outcome, verdict


async def run_items(
    items: Sequence[GoldenItem],
    *,
    settings: EvalSettings,
    llm_factory: LlmFactory,
    connector_factory: ConnectorFactory,
    sink: TraceSink,
    sleep: Sleep = asyncio.sleep,
) -> RunResult:
    """Collect every item in id order inside one sink run, then hand the verdicts to the sink.

    An item whose outcome is cached and whose trace still exists is not collected again (D-14),
    and feedback goes only to traces whose current verdict has not been attached yet.
    """
    config = WorkflowConfig(
        reformulate_model=settings.reformulate_model,
        answer_model=settings.answer_model,
        confidence_threshold=settings.confidence_threshold,
    )
    index = SourceIndex.open(settings.artifact_dir)
    identity = index.identity
    cache = ResultCache(settings.private_dir / "eval" / "cache")
    version = bot_version()
    tags = {
        "items": str(len(items)),
        "index_content_hash": identity.content_hash,
        "guides_commit_sha": identity.guides_commit_sha,
        "build_id": identity.build_id,
        "bot_version": version,
        "reformulate_model": settings.reformulate_model,
        "answer_model": settings.answer_model,
    }
    ordered = sorted(items, key=lambda item: item.id)
    outcomes: list[ItemOutcome] = []
    outcome_keys: list[str] = []
    consecutive_errors = 0
    aborted = False
    collected_any = False
    with sink.run(RUN_NAME, tags):
        for item in ordered:
            key = key_for(
                item=item.model_dump(mode="json"),
                content_hash=identity.content_hash,
                guides_commit_sha=identity.guides_commit_sha,
                bot_version=version,
                reformulate_model=settings.reformulate_model,
                answer_model=settings.answer_model,
                confidence_threshold=settings.confidence_threshold,
                outcome_schema=OUTCOME_SCHEMA_VERSION,
            )
            outcome = _cached_outcome(cache, key, item, sink)
            if outcome is None:
                if collected_any and settings.item_pause_seconds > 0:
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
                collected_any = True
                if outcome.status == "completed":
                    cache.put("outcome", key, _outcome_payload(outcome))
                LOGGER.info("item %s %s", item.id, outcome.status)
            else:
                LOGGER.info("item %s %s (cached)", item.id, outcome.status)
            outcomes.append(outcome)
            outcome_keys.append(key)
            # A completed item resets the run of errors; an errored one is never retried (D-14).
            consecutive_errors = consecutive_errors + 1 if outcome.status == "errored" else 0
            if consecutive_errors >= settings.max_consecutive_errors:
                LOGGER.warning("run stopped after %d consecutive errors", consecutive_errors)
                aborted = True
                break
        # Judge phase: one verdict per answered item, whatever its kind (D-10). Items after an
        # abort were never collected: they get no outcome and no verdict.
        judges: dict[str, JudgeVerdict] = {}
        for position, (item, key) in enumerate(zip(ordered, outcome_keys, strict=False)):
            outcomes[position], verdict = await _judge_item(
                item,
                outcomes[position],
                outcome_key=key,
                settings=settings,
                llm_factory=llm_factory,
                cache=cache,
                sink=sink,
            )
            if verdict is not None:
                judges[item.id] = verdict
        verdicts = tuple(
            score_item(item, outcome, resolve=index.resolve, judge=judges.get(item.id))
            for item, outcome in zip(ordered, outcomes, strict=False)
        )
        scored = {
            v.trace_id: v
            for v in verdicts
            if v.trace_id is not None
            and v.status != "errored"
            and not cache.is_scored(v.trace_id, scored_version(v))
        }
        sink.score(list(scored), scored)
        for trace_id, scored_verdict in scored.items():
            cache.mark_scored(trace_id, scored_version(scored_verdict))
    return RunResult(tuple(outcomes), verdicts, aborted=aborted, identity=identity)
