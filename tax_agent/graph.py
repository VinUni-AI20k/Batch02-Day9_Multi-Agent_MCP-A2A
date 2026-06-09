"""Tax Agent LangGraph definition — single-shot LLM node.

Replaced create_react_agent (which runs a multi-turn tool loop even with no tools)
with a direct ainvoke call, saving ~1 extra LLM round-trip per request.
"""

from __future__ import annotations

from typing import TypedDict

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph

from common.llm import content_to_str, get_llm

TAX_SYSTEM_PROMPT = """You are a specialist tax attorney. Respond in the same language as the question. Be concise (3-4 key points max).
Cover: civil vs criminal penalties, IRS/DOJ enforcement, statute of limitations, individual vs corporate liability.
Educational purposes only."""


class TaxState(TypedDict):
    messages: list


async def tax_node(state: TaxState) -> dict:
    llm = get_llm()
    user_msgs = [m for m in state["messages"] if isinstance(m, HumanMessage)]
    result = await llm.ainvoke([SystemMessage(content=TAX_SYSTEM_PROMPT)] + user_msgs)
    return {"messages": state["messages"] + [AIMessage(content=content_to_str(result.content))]}


def create_graph():
    graph = StateGraph(TaxState)
    graph.add_node("tax", tax_node)
    graph.set_entry_point("tax")
    graph.add_edge("tax", END)
    return graph.compile()
