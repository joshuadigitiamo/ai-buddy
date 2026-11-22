"""The empty-context test (EVAL-04, D-16): no source exists, so the bot must refuse everywhere.

Every approved handbook and Guides item goes through the real `run_workflow` against a second MCP
server whose index holds only unrelated fixture sources. The test passes only when every reply is
a refusal or a referral with a logged gap. A smalltalk reply is not a refusal, a referral without
a logged gap does not count, and an item that errored proves nothing, so it never counts as a pass.
Console output carries item ids, statuses, evidence counts and trace links; question and answer
text never leave the traces (T-05-29).
"""

from __future__ import annotations

import asyncio
import json
import logging
import urllib.parse
import urllib.request
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping, Sequence
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from dataclasses import dataclass
from typing import Any, Final, Literal, cast

from pydantic import ValidationError

from buddy_bot.mcp_client import McpToolError
from buddy_bot.ports import LlmClient, LlmError, McpConnector, McpTools
from buddy_bot.schemas import BotReply
from buddy_bot.workflow import WorkflowConfig, WorkflowDeps, run_workflow
from buddy_eval.cache import ResultCache, bot_version, key_for
from buddy_eval.config import EvalSettings
from buddy_eval.golden import GoldenItem
from buddy_eval.sources import SourceIndex
from buddy_eval.tracing import EMPTY_SCORER_SET_VERSION, TraceSink, TracingError
from buddy_mcp.models import GapReportOutput, GuidesSearchOutput, HandbookSearchOutput

LOGGER: Final = logging.getLogger("buddy_eval")
TRACE_NAME: Final = "bot_run"
RUN_NAME: Final = "empty-context"
# Bump when EmptyContextItem or the cached payload change shape: it is a key ingredient, so older
# cached outcomes stop matching instead of failing to load.
EMPTY_SCHEMA_VERSION: Final = 1
GAP_REQUEST_TIMEOUT_SECONDS: Final = 5
GAP_PAGE_SIZE: Final = 300
EXPECTED_OUTCOME: Final = "refusal_with_gap"

Status = Literal["refused", "answered", "no_gap", "smalltalk", "errored"]
LlmFactory = Callable[[], LlmClient]
ConnectorFactory = Callable[[str], McpConnector]
Sleep = Callable[[float], Awaitable[None]]
GapCounter = Callable[[str, str, str], int]
# An errored item is never cached, so a cached payload holds one of the others.
_CACHED_STATUSES: Final = ("refused", "answered", "no_gap", "smalltalk")


class GapCountError(RuntimeError):
    """The emulator could not be read; the message names no document content."""


@dataclass(frozen=True, slots=True)
class EmptyContextItem:
    """What the bot did for one item; `evidence_count` is the number of search results returned."""

    item_id: str
    status: Status
    reply_kind: str
    gap_reported: bool
    evidence_count: int
    trace_id: str | None


@dataclass(frozen=True, slots=True)
class EmptyContextResult:
    """Items in id order, the verdict and the outcome of the independent gap cross-check.

    `passed` is True only when every item is `refused`, no item errored, at least one item ran
    and the cross-check did not find fewer gap documents than gap_reported replies.
    """

    items: tuple[EmptyContextItem, ...]
    passed: bool
    gap_check: str
    gap_mismatch: bool = False

    def ids_with(self, status: Status) -> tuple[str, ...]:
        return tuple(
            i.item_id for i in sorted(self.items, key=lambda i: i.item_id) if i.status == status
        )


class _EvidenceCount:
    """Counts the search results one run saw, so an overlap with the fixture is visible."""

    def __init__(self) -> None:
        self.total = 0


class _CountingTools:
    def __init__(self, inner: McpTools, counter: _EvidenceCount) -> None:
        self._inner = inner
        self._counter = counter

    async def handbook_search(self, query: str) -> HandbookSearchOutput:
        found = await self._inner.handbook_search(query)
        self._counter.total += len(found.results)
        return found

    async def guides_search(self, query: str) -> GuidesSearchOutput:
        found = await self._inner.guides_search(query)
        self._counter.total += len(found.results)
        return found

    async def report_gap(self, question: str, tried: Sequence[str]) -> GapReportOutput:
        return await self._inner.report_gap(question, tried)


class _CountingConnector:
    def __init__(self, inner: McpConnector, counter: _EvidenceCount) -> None:
        self._inner = inner
        self._counter = counter

    def session(self) -> AbstractAsyncContextManager[McpTools]:
        return self._session()

    @asynccontextmanager
    async def _session(self) -> AsyncIterator[McpTools]:
        async with self._inner.session() as tools:
            yield _CountingTools(tools, self._counter)


def classify(reply: BotReply) -> Status:
    """Refusal or referral with a logged gap is `refused`; anything else is a failure or error."""
    if reply.kind == "error":
        return "errored"
    if reply.kind == "answer":
        return "answered"
    if reply.kind == "smalltalk":
        return "smalltalk"
    return "refused" if reply.gap_reported else "no_gap"


def count_gap_documents(host: str, project: str, collection: str) -> int:
    """Documents in a collection of the Firestore emulator, over its REST list endpoint.

    Follows `nextPageToken`; each request has a 5 s timeout. Raises GapCountError for anything
    that is not a readable list reply, never with document content.
    """
    base = (
        f"http://{host}/v1/projects/{urllib.parse.quote(project, safe='')}"
        f"/databases/(default)/documents/{urllib.parse.quote(collection, safe='')}"
    )
    total = 0
    token: str | None = None
    while True:
        query = {"pageSize": str(GAP_PAGE_SIZE)}
        if token is not None:
            query["pageToken"] = token
        url = f"{base}?{urllib.parse.urlencode(query)}"
        try:
            with urllib.request.urlopen(url, timeout=5) as response:  # noqa: S310 - http only
                page = json.loads(response.read().decode("utf-8"))
        except (OSError, ValueError) as exc:
            raise GapCountError(type(exc).__name__) from exc
        if not isinstance(page, dict):
            raise GapCountError("unexpected reply shape")
        documents = page.get("documents", [])
        if not isinstance(documents, list):
            raise GapCountError("unexpected reply shape")
        total += len(documents)
        next_token = page.get("nextPageToken")
        if not isinstance(next_token, str) or not next_token:
            return total
        token = next_token


def _payload(item: EmptyContextItem) -> dict[str, object]:
    return {
        "item_id": item.item_id,
        "status": item.status,
        "reply_kind": item.reply_kind,
        "gap_reported": item.gap_reported,
        "evidence_count": item.evidence_count,
        "trace_id": item.trace_id,
    }


def _from_payload(item: GoldenItem, payload: Mapping[str, Any]) -> EmptyContextItem | None:
    """Rebuild a cached item; None when the payload does not fit."""
    status = payload.get("status")
    trace_id = payload.get("trace_id")
    reply_kind = payload.get("reply_kind")
    gap = payload.get("gap_reported")
    evidence = payload.get("evidence_count")
    if payload.get("item_id") != item.id or status not in _CACHED_STATUSES:
        return None
    if not isinstance(trace_id, str) or not isinstance(reply_kind, str):
        return None
    if not isinstance(gap, bool) or not isinstance(evidence, int) or isinstance(evidence, bool):
        return None
    return EmptyContextItem(item.id, cast("Status", status), reply_kind, gap, evidence, trace_id)


def _cached(
    cache: ResultCache, key: str, item: GoldenItem, sink: TraceSink
) -> EmptyContextItem | None:
    """A cached item, only while its trace still exists; otherwise the item runs again."""
    payload = cache.get("empty_context", key)
    if payload is None:
        return None
    cached = _from_payload(item, payload)
    if cached is None or cached.trace_id is None or not sink.trace_exists(cached.trace_id):
        return None
    return cached


async def _collect(
    item: GoldenItem,
    *,
    config: WorkflowConfig,
    llm_factory: LlmFactory,
    connector_factory: ConnectorFactory,
    mcp_url: str,
    sink: TraceSink,
) -> EmptyContextItem:
    """Run one item through the bot against the fixture server, under one trace."""
    counter = _EvidenceCount()

    async def fn() -> dict[str, Any]:
        connector = _CountingConnector(connector_factory(mcp_url), counter)
        deps = WorkflowDeps(llm_factory(), connector, config)
        reply = await run_workflow(item.question, [], deps)
        return reply.model_dump(mode="json")

    try:
        output, trace_id = await sink.traced(TRACE_NAME, {"item_id": item.id, "run": RUN_NAME}, fn)
    except (LlmError, McpToolError) as exc:
        LOGGER.warning("item %s errored: %s", item.id, type(exc).__name__)
        return EmptyContextItem(item.id, "errored", "error", False, counter.total, None)
    except TracingError:
        raise
    except Exception as exc:  # noqa: BLE001 - a transport failure errors the item, never the run
        # Type name only: the message may carry a URL or request detail (T-05-53).
        LOGGER.warning("item %s errored: %s", item.id, type(exc).__name__)
        return EmptyContextItem(item.id, "errored", "error", False, counter.total, None)
    sink.log_expectations(trace_id, {"expected_outcome": EXPECTED_OUTCOME, "kind": item.kind})
    try:
        reply = BotReply.model_validate(output)
    except ValidationError:
        return EmptyContextItem(item.id, "errored", "error", False, counter.total, trace_id)
    return EmptyContextItem(
        item.id, classify(reply), reply.kind, reply.gap_reported, counter.total, trace_id
    )


def _answerable(items: Sequence[GoldenItem]) -> list[GoldenItem]:
    """Approved handbook and Guides items in id order (A-10-1)."""
    return sorted(
        (i for i in items if i.kind in ("handbook", "guides") and i.review == "approved"),
        key=lambda item: item.id,
    )


async def _check_gaps(
    settings: EvalSettings,
    count_gaps: GapCounter,
    *,
    before: int | None,
    fresh_gaps: int,
) -> tuple[str, bool]:
    """Compare the document count delta with the fresh gap_reported replies."""
    host = settings.firestore_emulator_host
    assert host is not None and before is not None
    try:
        after = await asyncio.to_thread(
            count_gaps, host, settings.google_cloud_project, settings.empty_gap_collection
        )
    except GapCountError as exc:
        return f"gap cross-check skipped (emulator unreadable: {exc})", False
    appeared = after - before
    if fresh_gaps and appeared < fresh_gaps:
        return (
            f"gap count mismatch ({appeared} documents for {fresh_gaps} gap_reported replies)",
            True,
        )
    return f"gap cross-check ok ({appeared} documents for {fresh_gaps} gap_reported replies)", False


def _verdict(items: Sequence[EmptyContextItem], *, mismatch: bool) -> bool:
    return bool(items) and not mismatch and all(i.status == "refused" for i in items)


async def run_empty_context(
    items: Sequence[GoldenItem],
    *,
    settings: EvalSettings,
    llm_factory: LlmFactory,
    connector_factory: ConnectorFactory,
    sink: TraceSink,
    cache: ResultCache,
    sleep: Sleep = asyncio.sleep,
    count_gaps: GapCounter = count_gap_documents,
) -> EmptyContextResult:
    """Run every approved answerable item against the fixture server, in id order.

    An item whose outcome is cached and whose trace still exists is not run again (D-14). The gap
    cross-check counts only freshly run items (A-10-2): cached ones wrote their gaps earlier.
    """
    ordered = _answerable(items)
    if not ordered:
        return EmptyContextResult((), False, "gap cross-check skipped (no items)")
    config = WorkflowConfig(
        reformulate_model=settings.reformulate_model,
        answer_model=settings.answer_model,
        confidence_threshold=settings.confidence_threshold,
    )
    identity = SourceIndex.open(settings.fixture_dir).identity
    version = bot_version()
    keys = {
        item.id: key_for(
            item=item.model_dump(mode="json"),
            fixture_content_hash=identity.content_hash,
            bot_version=version,
            reformulate_model=settings.reformulate_model,
            answer_model=settings.answer_model,
            confidence_threshold=settings.confidence_threshold,
            empty_schema=EMPTY_SCHEMA_VERSION,
        )
        for item in ordered
    }
    done: dict[str, EmptyContextItem] = {}
    for item in ordered:
        hit = _cached(cache, keys[item.id], item, sink)
        if hit is not None:
            done[item.id] = hit
            LOGGER.info("item %s %s (cached)", item.id, hit.status)
    pending = [item for item in ordered if item.id not in done]

    host = settings.firestore_emulator_host
    before: int | None = None
    gap_check = "gap cross-check skipped (FIRESTORE_EMULATOR_HOST unset)"
    if not pending:
        gap_check = "gap cross-check skipped (no fresh items)"
    elif host:
        try:
            before = await asyncio.to_thread(
                count_gaps, host, settings.google_cloud_project, settings.empty_gap_collection
            )
        except GapCountError as exc:
            gap_check = f"gap cross-check skipped (emulator unreadable: {exc})"

    fresh_gaps = 0
    for position, item in enumerate(pending):
        if position and settings.item_pause_seconds > 0:
            # The MCP server rate limit counts every request (RESEARCH Pitfall 7).
            await sleep(settings.item_pause_seconds)
        outcome = await _collect(
            item,
            config=config,
            llm_factory=llm_factory,
            connector_factory=connector_factory,
            mcp_url=settings.mcp_empty_url,
            sink=sink,
        )
        done[item.id] = outcome
        if outcome.status == "errored":
            continue
        cache.put("empty_context", keys[item.id], _payload(outcome))
        LOGGER.info("item %s %s", item.id, outcome.status)
        fresh_gaps += 1 if outcome.gap_reported else 0

    mismatch = False
    if pending and host and before is not None:
        gap_check, mismatch = await _check_gaps(
            settings, count_gaps, before=before, fresh_gaps=fresh_gaps
        )
    result_items = tuple(done[item.id] for item in ordered)
    return EmptyContextResult(
        result_items, _verdict(result_items, mismatch=mismatch), gap_check, mismatch
    )


def _segment(label: str, ids: tuple[str, ...]) -> str | None:
    return f"{len(ids)} {label}: {', '.join(ids)}" if ids else None


def format_empty_context(
    result: EmptyContextResult, *, trace_url: Callable[[str], str] | None = None
) -> list[str]:
    """Item lines in id order, the gap cross-check line and the verdict line."""
    lines = []
    for item in sorted(result.items, key=lambda i: i.item_id):
        if item.trace_id is None:
            trace = "none"
        else:
            trace = trace_url(item.trace_id) if trace_url is not None else item.trace_id
        lines.append(f"{item.item_id} {item.status} evidence={item.evidence_count} trace={trace}")
    if not result.items:
        return ["empty_context: FAIL (no approved answerable items)"]
    lines.append(result.gap_check)
    failures = [
        _segment("answered", result.ids_with("answered")),
        _segment("smalltalk", result.ids_with("smalltalk")),
        _segment("without gap", result.ids_with("no_gap")),
    ]
    errored = _segment("errored", result.ids_with("errored"))
    parts = [part for part in failures if part is not None]
    if result.gap_mismatch:
        parts.append(result.gap_check)
    if parts:
        if errored is not None:
            parts.append(errored)
        lines.append(f"empty_context: FAIL ({'; '.join(parts)})")
    elif errored is not None:
        lines.append(f"empty_context: INCOMPLETE ({errored})")
    else:
        total = len(result.items)
        lines.append(f"empty_context: PASS ({total}/{total} refused with gap)")
    return lines


def payload(result: EmptyContextResult) -> dict[str, object]:
    """The JSON report: per-item status and evidence counts, no text."""
    return {
        "passed": result.passed,
        "gap_check": result.gap_check,
        "items": [_payload(item) for item in sorted(result.items, key=lambda i: i.item_id)],
    }


def empty_scored_version(item: EmptyContextItem) -> str:
    """The scored marker of an item's trace; a changed status makes it score again."""
    return f"{EMPTY_SCORER_SET_VERSION}-{item.status}"


def unscored(result: EmptyContextResult, cache: ResultCache) -> dict[str, EmptyContextItem]:
    """Items with a trace that has no feedback of the empty-context scorer set yet."""
    return {
        item.trace_id: item
        for item in result.items
        if item.trace_id is not None
        and item.status != "errored"
        and not cache.is_scored(item.trace_id, empty_scored_version(item))
    }
