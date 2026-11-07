"""LangGraph 2-step RAG: reformulate, retrieve through MCP, answer, citation gate.

Dependencies reach the nodes through `runtime.context`, never through state. Routing uses
conditional edges only. The graph has no persistence layer: thread memory is a port (D-10).
"""

from collections.abc import Sequence
from dataclasses import dataclass
from functools import cache
from typing import Any, Final, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime

from buddy_bot.gate import check, cited_sources
from buddy_bot.mcp_client import evidence_from
from buddy_bot.ports import LlmClient, McpConnector, McpTools, Turn
from buddy_bot.prompts import ANSWER_SYSTEM, REFORMULATE_SYSTEM, format_evidence, format_history
from buddy_bot.schemas import AnswerDraft, BotReply, Evidence, Referente, Reformulation

REFORMULATE_MAX_TOKENS: Final = 600
ANSWER_MAX_TOKENS: Final = 1500

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


@dataclass(frozen=True, slots=True)
class RunContext:
    """Per-run dependencies, read by nodes from `runtime.context`."""

    llm: LlmClient
    tools: McpTools
    config: WorkflowConfig


class State(TypedDict, total=False):
    question: str
    history: Sequence[Turn]
    reformulation: Reformulation
    evidence: dict[str, Evidence]
    tried: list[str]
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
    reformulation = state["reformulation"]
    handbook_query = " ".join(reformulation.keywords_it)
    guides_query = " ".join(reformulation.keywords_en)
    handbook = await tools.handbook_search(handbook_query)
    guides = await tools.guides_search(guides_query)
    return {
        "evidence": evidence_from(handbook, guides),
        "tried": [f"handbook_search: {handbook_query}", f"guides_search: {guides_query}"],
    }


async def answer(state: State, runtime: Runtime[RunContext]) -> dict[str, Any]:
    ctx = runtime.context
    user = (
        f"Domanda: {state['reformulation'].standalone_question}\n\n"
        f"{format_evidence(list(state['evidence'].values()))}"
    )
    draft = await ctx.llm.structured(
        AnswerDraft,
        model=ctx.config.answer_model,
        system=ANSWER_SYSTEM,
        user=user,
        max_tokens=ANSWER_MAX_TOKENS,
    )
    return {"draft": draft}


async def gate(state: State, runtime: Runtime[RunContext]) -> dict[str, Any]:
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
    reply = BotReply(
        kind="refusal", referente=Referente(role="HR"), gate_reason=state.get("gate_reason")
    )
    return {"reply": reply}


def _after_retrieve(state: State) -> str:
    return "answer" if state["evidence"] else "gate"


def _after_gate(state: State) -> str:
    return "finish" if state["gate_reason"] == "ok" else "refuse"


def build_graph() -> Any:
    """Compile the graph once; nodes read their dependencies from `runtime.context`."""
    graph = StateGraph(State, context_schema=RunContext)
    graph.add_node("reformulate", reformulate)
    graph.add_node("retrieve", retrieve)
    graph.add_node("answer", answer)
    graph.add_node("gate", gate)
    graph.add_node("finish", finish)
    graph.add_node("refuse", refuse)
    graph.add_edge(START, "reformulate")
    graph.add_edge("reformulate", "retrieve")
    graph.add_conditional_edges("retrieve", _after_retrieve, ["answer", "gate"])
    graph.add_edge("answer", "gate")
    graph.add_conditional_edges("gate", _after_gate, ["finish", "refuse"])
    graph.add_edge("finish", END)
    graph.add_edge("refuse", END)
    return graph.compile()


@cache
def _graph() -> Any:
    return build_graph()


async def run_workflow(question: str, history: Sequence[Turn], deps: WorkflowDeps) -> BotReply:
    """Run one question through the graph inside one MCP session and return the reply."""
    async with deps.mcp.session() as tools:
        context = RunContext(llm=deps.llm, tools=tools, config=deps.config)
        final: State = await _graph().ainvoke(
            {"question": question, "history": history}, context=context
        )
    return final["reply"]
