"""Recall@5 of the two search tools over the approved answerable items (D-15, EVAL-02).

The query of each item is the one the bot itself would send: the keywords of the real
`reformulate` node, joined by spaces. Reformulations are cached, so a second run makes no model
call. One MCP session serves every item and no trace is created. Output is limited to item ids,
numbers and the D5 trigger line; question text and retrieved ids stay out of the console.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import Final, Literal

from langgraph.runtime import Runtime
from pydantic import ValidationError

from buddy_bot.mcp_client import FastMcpConnector, McpToolError
from buddy_bot.ports import LlmClient, McpConnector
from buddy_bot.prompts import build_reformulate_system
from buddy_bot.schemas import Reformulation
from buddy_bot.workflow import RunContext, WorkflowConfig, reformulate
from buddy_core.escalation import load_escalation_table
from buddy_eval.cache import ResultCache, bot_version, key_for
from buddy_eval.config import EvalSettings
from buddy_eval.golden import GoldenItem
from buddy_eval.sources import matches

LOGGER: Final = logging.getLogger("buddy_eval")
TOP_K: Final = 5
GUIDES_TARGET_NUMERATOR: Final = 4
GUIDES_TARGET_DENOMINATOR: Final = 5
D5_TRIGGER_LINE: Final = (
    "D5 TRIGGER: guides recall@5 < 0.8 -> plan the hybrid dense+BM25 upgrade (RET-01)"
)
_NON_QUESTION_INTENTS: Final = frozenset({"chitchat", "off_topic"})

Source = Literal["handbook", "guides"]
ConnectorFactory = Callable[[str], McpConnector]
LlmFactory = Callable[[], LlmClient]
Sleep = Callable[[float], Awaitable[None]]


def default_connector_factory(url: str) -> McpConnector:
    """The connector of the recall measurement: the top five results of both tools (D-15)."""
    return FastMcpConnector(url, handbook_limit=5, guides_limit=5)


@dataclass(frozen=True, slots=True)
class RecallItem:
    """The outcome for one item; `retrieved` holds private ids and never reaches the console."""

    item_id: str
    source: Source
    hit: bool
    fraction: float
    errored: bool
    retrieved: tuple[str, ...]
    intent: str = ""


@dataclass(frozen=True, slots=True)
class RecallResult:
    """Hit rate per source over the measured (non-errored) items, plus the D5 trigger."""

    items: tuple[RecallItem, ...]
    handbook_hits: int
    handbook_total: int
    guides_hits: int
    guides_total: int
    handbook_fraction: float
    guides_fraction: float
    errored_ids: tuple[str, ...]
    trigger: bool

    @property
    def non_question_count(self) -> int:
        """Items the bot reformulated as chitchat or off-topic (A-09-1)."""
        return sum(1 for item in self.items if item.intent in _NON_QUESTION_INTENTS)


def _source_of(item: GoldenItem) -> Source:
    return "handbook" if item.kind == "handbook" else "guides"


def _score(expected: Sequence[str], retrieved: Sequence[str]) -> tuple[bool, float]:
    """Hit when any expected entry is among the retrieved keys; the fraction counts each
    expected entry once, however many results match it."""
    found = sum(1 for entry in expected if any(matches(key, entry) for key in retrieved))
    return found > 0, found / len(expected) if expected else 0.0


def _reformulation_key(settings: EvalSettings, question: str) -> str:
    system_hash = hashlib.sha256(
        build_reformulate_system(load_escalation_table()).encode("utf-8")
    ).hexdigest()
    return key_for(
        question=question,
        reformulate_model=settings.reformulate_model,
        system_hash=system_hash,
        bot_version=bot_version(),
    )


def _cached_reformulation(cache: ResultCache, key: str) -> Reformulation | None:
    payload = cache.get("reformulation", key)
    if payload is None:
        return None
    try:
        return Reformulation.model_validate(payload)
    except ValidationError:
        return None


def _errored(item: GoldenItem) -> RecallItem:
    return RecallItem(item.id, _source_of(item), False, 0.0, True, ())


def _summarise(items: tuple[RecallItem, ...]) -> RecallResult:
    def totals(source: Source) -> tuple[int, int, float]:
        measured = [i for i in items if i.source == source and not i.errored]
        hits = sum(1 for i in measured if i.hit)
        fraction = sum(i.fraction for i in measured) / len(measured) if measured else 0.0
        return hits, len(measured), fraction

    handbook_hits, handbook_total, handbook_fraction = totals("handbook")
    guides_hits, guides_total, guides_fraction = totals("guides")
    return RecallResult(
        items=items,
        handbook_hits=handbook_hits,
        handbook_total=handbook_total,
        guides_hits=guides_hits,
        guides_total=guides_total,
        handbook_fraction=handbook_fraction,
        guides_fraction=guides_fraction,
        errored_ids=tuple(i.item_id for i in items if i.errored),
        # Integer arithmetic: exactly 0.8 must not trigger (EVAL-02 adjacency).
        trigger=guides_total > 0
        and guides_hits * GUIDES_TARGET_DENOMINATOR < guides_total * GUIDES_TARGET_NUMERATOR,
    )


async def measure_recall(
    items: Sequence[GoldenItem],
    *,
    settings: EvalSettings,
    llm_factory: LlmFactory,
    cache: ResultCache,
    connector_factory: ConnectorFactory = default_connector_factory,
    sleep: Sleep = asyncio.sleep,
) -> RecallResult:
    """Search with the bot's reformulation of every handbook and Guides item, in id order.

    A failed reformulation or tool call errors the item; it is never counted as a miss.
    """
    config = WorkflowConfig(
        reformulate_model=settings.reformulate_model,
        answer_model=settings.answer_model,
        confidence_threshold=settings.confidence_threshold,
    )
    ordered = sorted(
        (i for i in items if i.kind in ("handbook", "guides")), key=lambda item: item.id
    )
    if not ordered:
        return _summarise(())
    llm: LlmClient | None = None
    measured: list[RecallItem] = []
    async with connector_factory(settings.mcp_url).session() as tools:
        for position, item in enumerate(ordered):
            if position and settings.item_pause_seconds > 0:
                # The MCP server rate limit counts every request (RESEARCH Pitfall 7).
                await sleep(settings.item_pause_seconds)
            key = _reformulation_key(settings, item.question)
            reformulation = _cached_reformulation(cache, key)
            if reformulation is None:
                llm = llm if llm is not None else llm_factory()
                runtime = Runtime(context=RunContext(llm=llm, tools=tools, config=config))
                update = await reformulate({"question": item.question, "history": []}, runtime)
                reformulation = update.get("reformulation")
                if reformulation is None:
                    LOGGER.warning("item %s reformulation failed", item.id)
                    measured.append(_errored(item))
                    continue
                cache.put("reformulation", key, reformulation.model_dump(mode="json"))
            try:
                if item.kind == "handbook":
                    found = await tools.handbook_search(" ".join(reformulation.keywords_it))
                    retrieved = tuple(r.source_url for r in found.results[:TOP_K])
                else:
                    guides = await tools.guides_search(" ".join(reformulation.keywords_en))
                    retrieved = tuple(r.section_id for r in guides.results[:TOP_K])
            except McpToolError as exc:
                LOGGER.warning("item %s search failed: %s", item.id, exc)
                measured.append(_errored(item))
                continue
            hit, fraction = _score(item.expected_sources, retrieved)
            measured.append(
                RecallItem(
                    item.id, _source_of(item), hit, fraction, False, retrieved, reformulation.intent
                )
            )
            LOGGER.info("item %s recall %s", item.id, "hit" if hit else "miss")
    return _summarise(tuple(measured))


def _rate_line(source: Source, hits: int, total: int, fraction: float, items: int) -> str:
    label = f"recall@5 {source}: "
    if total == 0:
        return label + ("n/a (0 items)" if items == 0 else "n/a (0 measured)")
    return label + f"{hits / total:.2f} ({hits}/{total}; fractional {fraction:.2f})"


def format_recall(result: RecallResult) -> list[str]:
    """Console lines: both rates, the D5 trigger or its warning, information, INCOMPLETE."""
    by_source = {s: sum(1 for i in result.items if i.source == s) for s in ("handbook", "guides")}
    lines = [
        _rate_line(
            "handbook",
            result.handbook_hits,
            result.handbook_total,
            result.handbook_fraction,
            by_source["handbook"],
        ),
        _rate_line(
            "guides",
            result.guides_hits,
            result.guides_total,
            result.guides_fraction,
            by_source["guides"],
        ),
    ]
    if result.trigger:
        lines.append(D5_TRIGGER_LINE)
    elif result.guides_total == 0:
        lines.append("warning: no guides item measured, the D5 trigger cannot be evaluated")
    if result.non_question_count:
        lines.append(
            f"info: {result.non_question_count} items reformulated as chitchat or off_topic "
            "(search still ran)"
        )
    if result.errored_ids:
        lines.append(
            f"recall: INCOMPLETE ({len(result.errored_ids)} errored: "
            f"{', '.join(result.errored_ids)})"
        )
    return lines


def payload(result: RecallResult) -> dict[str, object]:
    """The private JSON report: per-item hits and the retrieved ids (private page ids)."""
    return {
        "handbook": {
            "hits": result.handbook_hits,
            "total": result.handbook_total,
            "fractional": result.handbook_fraction,
        },
        "guides": {
            "hits": result.guides_hits,
            "total": result.guides_total,
            "fractional": result.guides_fraction,
        },
        "trigger": result.trigger,
        "errored": list(result.errored_ids),
        "items": [
            {
                "id": i.item_id,
                "source": i.source,
                "hit": i.hit,
                "fraction": i.fraction,
                "errored": i.errored,
                "intent": i.intent,
                "retrieved": list(i.retrieved),
            }
            for i in result.items
        ],
    }
