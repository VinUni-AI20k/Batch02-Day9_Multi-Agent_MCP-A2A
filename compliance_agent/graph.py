"""Compliance Agent LangGraph definition — single-shot LLM node.

Replaced create_react_agent with a direct ainvoke call to avoid the
multi-turn react loop overhead when no tools are registered.
"""

from __future__ import annotations

from typing import TypedDict

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph

from common.llm import content_to_str, get_llm

COMPLIANCE_SYSTEM_PROMPT = """You are a regulatory compliance attorney. Respond in the same language as the question. Be concise (3-4 key points max).
Cover: which agency has jurisdiction (SEC/FTC/DOJ), civil/criminal remedies, C-suite liability, mitigating factors.
Educational purposes only."""


class ComplianceState(TypedDict):
    messages: list


async def compliance_node(state: ComplianceState) -> dict:
    llm = get_llm()
    user_msgs = [m for m in state["messages"] if isinstance(m, HumanMessage)]
    result = await llm.ainvoke([SystemMessage(content=COMPLIANCE_SYSTEM_PROMPT)] + user_msgs)
    return {"messages": state["messages"] + [AIMessage(content=content_to_str(result.content))]}


def create_graph():
    graph = StateGraph(ComplianceState)
    graph.add_node("compliance", compliance_node)
    graph.set_entry_point("compliance")
    graph.add_edge("compliance", END)
    return graph.compile()
