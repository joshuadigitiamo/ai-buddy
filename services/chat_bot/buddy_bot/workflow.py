"""LangGraph 2-step RAG: reformulate, retrieve through MCP, answer, citation gate.

A failed gate gets exactly one retry with new keywords, then a refusal naming a referente.
The gap is written once by `run_workflow` after the graph returns, never inside a node, so a
graph re-execution cannot log it twice. Dependencies reach the nodes through
`runtime.context`, never through state. Routing uses conditional edges only. The graph has no
persistence layer: thread memory is a port (D-10).
"""

import logging
from collections.abc import Sequence
from dataclasses import dataclass, field
from functools import cache
from typing import Any, Final, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime

from buddy_bot.gate import check, cited_sources
from buddy_bot.mcp_client import McpToolError, evidence_from
from buddy_bot.ports import LlmClient, LlmOutputError, McpConnector, McpTools, Turn
from buddy_bot.prompts import (
    ANSWER_SYSTEM,
    REFORMULATE_SYSTEM,
    RETRY_SYSTEM,
    format_evidence,
    format_history,
)
from buddy_bot.referral import resolve_referente
from buddy_bot.schemas import AnswerDraft, BotReply, Evidence, Reformulation, RetryPlan
from buddy_core.escalation import EscalationTable, load_escalation_table

REFORMULATE_MAX_TOKENS: Final = 600
ANSWER_MAX_TOKENS: Final = 1500
RETRY_MAX_TOKENS: Final = 300

_LOGGER = logging.getLogger("buddy_bot")

_NO_DRAFT: Final = AnswerDraft(answer="", citations=[], grounded=False, confidence=0.0)


@dataclass(frozen=True, slots=True)
class WorkflowConfig:
    reformulate_model: str
    answer_model: str
    confidence_threshold: float


@dataclass(frozen=True, slots=True)
class WorkflowDeps:
    llm: LlmClient
    mcp: McpConnector
    config: WorkflowConfig
    escalation: EscalationTable = field(default_factory=load_escalation_table)


@dataclass(frozen=True, slots=True)
class RunContext:
    """Per-run dependencies, read by nodes from `runtime.context`."""

    llm: LlmClient
    tools: McpTools
    config: WorkflowConfig
    escalation: EscalationTable = field(default_factory=load_escalation_table)


class State(TypedDict, total=False):
    question: str
    history: Sequence[Turn]
    reformulation: Reformulation
    evidence: dict[str, Evidence]
    tried: list[str]
    attempt: int
    retry: RetryPlan
    found: bool
    answer_failed: bool
    draft: AnswerDraft
    gate_reason: str
    reply: BotReply


async def reformulate(state: State, runtime: Runtime[RunContext]) -> dict[str, Any]:
    ctx = runtime.context
    history = format_history(state["history"])
    user = f"{history}\n\nMessaggio: {state['question']}" if history else state["question"]
    reformulation = await ctx.llm.structured(
        Reformulation,
        model=ctx.config.reformulate_model,
        system=REFORMULATE_SYSTEM,
        user=user,
        max_tokens=REFORMULATE_MAX_TOKENS,
    )
    return {"reformulation": reformulation}


async def retrieve(state: State, runtime: Runtime[RunContext]) -> dict[str, Any]:
    tools = runtime.context.tools
    plan = state.get("retry")
    reformulation = state["reformulation"]
    handbook_query = " ".join((plan or reformulation).keywords_it)
    guides_query = " ".join((plan or reformulation).keywords_en)
    handbook = await tools.handbook_search(handbook_query)
    guides = await tools.guides_search(guides_query)
    found = evidence_from(handbook, guides)
    update: dict[str, Any] = {
        "evidence": {**state.get("evidence", {}), **found},
        "tried": [
            *state.get("tried", []),
            f"handbook_search: {handbook_query}",
            f"guides_search: {guides_query}",
        ],
        "found": bool(found),
    }
    if not found:
        update["gate_reason"] = "no_evidence"
    return update


async def retry_plan(state: State, runtime: Runtime[RunContext]) -> dict[str, Any]:
    """Ask for different keywords once; an invalid output skips the retry (D-03)."""
    ctx = runtime.context
    user = (
        f"Domanda: {state['reformulation'].standalone_question}\n"
        f"Ricerche già provate: {'; '.join(state.get('tried', []))}\n"
        f"Motivo del fallimento: {state.get('gate_reason', 'unknown')}"
    )
    try:
        plan = await ctx.llm.structured(
            RetryPlan,
            model=ctx.config.reformulate_model,
            system=RETRY_SYSTEM,
            user=user,
            max_tokens=RETRY_MAX_TOKENS,
        )
    except LlmOutputError:
        return {"attempt": 1}
    return {"attempt": 1, "retry": plan}


async def answer(state: State, runtime: Runtime[RunContext]) -> dict[str, Any]:
    ctx = runtime.context
    user = (
        f"Domanda: {state['reformulation'].standalone_question}\n\n"
        f"{format_evidence(list(state['evidence'].values()))}"
    )
    try:
        draft = await ctx.llm.structured(
            AnswerDraft,
            model=ctx.config.answer_model,
            system=ANSWER_SYSTEM,
            user=user,
            max_tokens=ANSWER_MAX_TOKENS,
        )
    except LlmOutputError:
        return {"draft": _NO_DRAFT, "answer_failed": True}
    return {"draft": draft, "answer_failed": False}


async def gate(state: State, runtime: Runtime[RunContext]) -> dict[str, Any]:
    if state.get("answer_failed"):
        return {"gate_reason": "invalid_output"}
    result = check(
        state["evidence"],
        state.get("draft", _NO_DRAFT),
        runtime.context.config.confidence_threshold,
    )
    return {"gate_reason": result.reason}


async def finish(state: State, runtime: Runtime[RunContext]) -> dict[str, Any]:
    draft = state["draft"]
    reply = BotReply(
        kind="answer", answer=draft.answer, sources=cited_sources(state["evidence"], draft)
    )
    return {"reply": reply}


async def refuse(state: State, runtime: Runtime[RunContext]) -> dict[str, Any]:
    ctx = runtime.context
    referente = await resolve_referente(
        ctx.escalation.referente_role(None),
        tools=ctx.tools,
        llm=ctx.llm,
        model=ctx.config.reformulate_model,
    )
    reply = BotReply(kind="refusal", referente=referente, gate_reason=state.get("gate_reason"))
    return {"reply": reply}


def _decide(state: State) -> str:
    """After a failed or skipped attempt: the first failure retries, the second refuses."""
    if state["gate_reason"] == "ok":
        return "finish"
    return "retry_plan" if state.get("attempt", 0) == 0 else "refuse"


def _after_retrieve(state: State) -> str:
    return "answer" if state["found"] else _decide(state)


def _after_retry_plan(state: State) -> str:
    return "retrieve" if "retry" in state else "refuse"


def build_graph() -> Any:
    """Compile the graph once; nodes read their dependencies from `runtime.context`."""
    graph = StateGraph(State, context_schema=RunContext)
    graph.add_node("reformulate", reformulate)
    graph.add_node("retrieve", retrieve)
    graph.add_node("retry_plan", retry_plan)
    graph.add_node("answer", answer)
    graph.add_node("gate", gate)
    graph.add_node("finish", finish)
    graph.add_node("refuse", refuse)
    graph.add_edge(START, "reformulate")
    graph.add_edge("reformulate", "retrieve")
    graph.add_conditional_edges("retrieve", _after_retrieve, ["answer", "retry_plan", "refuse"])
    graph.add_edge("answer", "gate")
    graph.add_conditional_edges("gate", _decide, ["finish", "retry_plan", "refuse"])
    graph.add_conditional_edges("retry_plan", _after_retry_plan, ["retrieve", "refuse"])
    graph.add_edge("finish", END)
    graph.add_edge("refuse", END)
    return graph.compile()


@cache
def _graph() -> Any:
    return build_graph()


async def _log_gap(tools: McpTools, final: State, reply: BotReply) -> BotReply:
    """Record the unanswered question once: the standalone question, never a user identity."""
    question = final["reformulation"].standalone_question
    try:
        await tools.report_gap(question, final.get("tried", []))
    except McpToolError as exc:
        _LOGGER.error("gap report failed: %s", type(exc).__name__)
        return reply
    return reply.model_copy(update={"gap_reported": True})


async def run_workflow(question: str, history: Sequence[Turn], deps: WorkflowDeps) -> BotReply:
    """Run one question through the graph inside one MCP session and return the reply."""
    async with deps.mcp.session() as tools:
        context = RunContext(
            llm=deps.llm, tools=tools, config=deps.config, escalation=deps.escalation
        )
        final: State = await _graph().ainvoke(
            {"question": question, "history": history}, context=context
        )
        reply = final["reply"]
        if reply.kind in ("refusal", "referral"):
            reply = await _log_gap(tools, final, reply)
    return reply
