"""Law Agent LangGraph StateGraph definition.

Graph topology:
    analyze_law → check_routing → (parallel) call_tax + call_compliance → aggregate → END

The parallel branches (call_tax / call_compliance) are dispatched via LangGraph's
Send API so that both sub-agent calls happen concurrently.
"""

from __future__ import annotations

import json
import logging
from typing import Annotated, TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.constants import Send
from langgraph.graph import END, StateGraph

from common.llm import content_to_str, get_llm

logger = logging.getLogger(__name__)

MAX_DELEGATION_DEPTH = 3


# ---------------------------------------------------------------------------
# State definition
# ---------------------------------------------------------------------------

def _last_wins(a: str, b: str) -> str:
    """Reducer: keep the most recently written value."""
    return b if b else a


class LawState(TypedDict):
    question: str
    context_id: str
    trace_id: str
    delegation_depth: int
    law_analysis: str
    needs_tax: bool
    needs_compliance: bool
    # Annotated so parallel branches can both write without conflict
    tax_result: Annotated[str, _last_wins]
    compliance_result: Annotated[str, _last_wins]
    final_answer: str


# ---------------------------------------------------------------------------
# Node implementations
# ---------------------------------------------------------------------------

async def analyze_and_route(state: LawState) -> dict:
    """Single LLM call: legal analysis + routing decision combined.

    Replaces the previous two-step analyze_law → check_routing sequence,
    saving one full LLM round-trip (~15s on local models).
    """
    depth = state.get("delegation_depth", 0)
    if depth >= MAX_DELEGATION_DEPTH:
        logger.info("Max delegation depth reached (%d); skipping sub-agents", depth)
        # Still do analysis but skip delegation
        llm = get_llm()
        result = await llm.ainvoke([
            SystemMessage(content="You are a senior corporate litigation attorney. Analyse the legal aspects of the question."),
            HumanMessage(content=state["question"]),
        ])
        return {"law_analysis": content_to_str(result.content), "needs_tax": False, "needs_compliance": False}

    llm = get_llm()
    messages = [
        SystemMessage(
            content=(
                "You are a corporate litigation attorney. Respond in the same language as the question.\n"
                "Reply ONLY with valid JSON (no markdown):\n"
                '{"law_analysis":"<concise legal analysis, 3-4 key points>","needs_tax":<true|false>,"needs_compliance":<true|false>}\n'
                "needs_tax=true → involves tax law, IRS, tax evasion\n"
                "needs_compliance=true → involves SEC, SOX, AML, FCPA, regulatory bodies"
            )
        ),
        HumanMessage(content=state["question"]),
    ]
    result = await llm.ainvoke(messages)
    raw = content_to_str(result.content).strip()

    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    try:
        parsed = json.loads(raw)
        law_analysis = parsed.get("law_analysis", raw)
        needs_tax = bool(parsed.get("needs_tax", True))
        needs_compliance = bool(parsed.get("needs_compliance", True))
    except json.JSONDecodeError:
        logger.warning("Combined LLM returned non-JSON; using raw as analysis, routing both=True")
        law_analysis = raw
        needs_tax = True
        needs_compliance = True

    logger.info("analyze_and_route: needs_tax=%s needs_compliance=%s", needs_tax, needs_compliance)
    return {"law_analysis": law_analysis, "needs_tax": needs_tax, "needs_compliance": needs_compliance}


def route_to_subagents(state: LawState) -> list[Send]:
    """Dispatch parallel Send objects based on routing flags from analyze_and_route."""
    sends: list[Send] = []
    if state.get("needs_tax"):
        sends.append(Send("call_tax", state))
    if state.get("needs_compliance"):
        sends.append(Send("call_compliance", state))
    if not sends:
        sends.append(Send("aggregate", state))
    return sends


async def call_tax(state: LawState) -> dict:
    """Delegate to the Tax Agent via A2A."""
    from common.a2a_client import delegate
    from common.registry_client import discover

    try:
        endpoint = await discover("tax_question")
        result = await delegate(
            endpoint=endpoint,
            question=state["question"],
            context_id=state["context_id"],
            trace_id=state["trace_id"],
            depth=state.get("delegation_depth", 0) + 1,
        )
        logger.info("Tax Agent returned %d chars", len(result))
        return {"tax_result": result}
    except Exception as exc:
        logger.exception("call_tax failed: %s", exc)
        return {"tax_result": f"[Tax analysis unavailable: {exc}]"}


async def call_compliance(state: LawState) -> dict:
    """Delegate to the Compliance Agent via A2A."""
    from common.a2a_client import delegate
    from common.registry_client import discover

    try:
        endpoint = await discover("compliance_question")
        result = await delegate(
            endpoint=endpoint,
            question=state["question"],
            context_id=state["context_id"],
            trace_id=state["trace_id"],
            depth=state.get("delegation_depth", 0) + 1,
        )
        logger.info("Compliance Agent returned %d chars", len(result))
        return {"compliance_result": result}
    except Exception as exc:
        logger.exception("call_compliance failed: %s", exc)
        return {"compliance_result": f"[Compliance analysis unavailable: {exc}]"}


async def aggregate(state: LawState) -> dict:
    """Combine specialist results into a structured final answer — no LLM call.

    Skipping the synthesis LLM pass saves ~20s while preserving all analysis.
    Each section is already well-formed from its specialist agent.
    """
    sections: list[str] = []
    if state.get("law_analysis"):
        sections.append(f"## Legal Analysis\n\n{state['law_analysis']}")
    if state.get("tax_result"):
        sections.append(f"## Tax Analysis\n\n{state['tax_result']}")
    if state.get("compliance_result"):
        sections.append(f"## Regulatory Compliance Analysis\n\n{state['compliance_result']}")

    final = "\n\n---\n\n".join(sections)
    final += (
        "\n\n---\n\n"
        "*This analysis is provided for educational purposes only. "
        "Please consult a licensed attorney for advice specific to your situation.*"
    )
    return {"final_answer": final}


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------

def create_graph():
    """Build and compile the Law Agent StateGraph.

    Topology: analyze_and_route → [call_tax || call_compliance] → aggregate → END
    Two LLM calls saved vs original: merged analysis+routing, removed aggregate LLM.
    """
    graph = StateGraph(LawState)

    graph.add_node("analyze_and_route", analyze_and_route)
    graph.add_node("call_tax", call_tax)
    graph.add_node("call_compliance", call_compliance)
    graph.add_node("aggregate", aggregate)

    graph.set_entry_point("analyze_and_route")

    graph.add_conditional_edges(
        "analyze_and_route",
        route_to_subagents,
        ["call_tax", "call_compliance", "aggregate"],
    )

    graph.add_edge("call_tax", "aggregate")
    graph.add_edge("call_compliance", "aggregate")
    graph.add_edge("aggregate", END)

    return graph.compile()