"""Stage 4: Multi-Agent System (In-Process).

Multiple specialised agents collaborate on a complex legal question.
This mirrors Stage 5's architecture (law_agent/graph.py) but runs
entirely in-process: no HTTP, no A2A protocol, no separate servers.

Graph: analyze_law -> check_routing -> parallel [tax, compliance, privacy]
-> aggregate -> END
"""

import asyncio
import os
import sys
from typing import Annotated, TypedDict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import tool
from langgraph.types import Send
from langgraph.graph import END, StateGraph

from common.llm import get_llm


# ---------------------------------------------------------------------------
# Tools for specialist sub-agents
# ---------------------------------------------------------------------------


@tool
def search_tax_law(query: str) -> str:
    """Search tax law knowledge base for relevant statutes and penalties.

    Args:
        query: Natural language query about tax law.
    """
    knowledge = [
        (
            ["tax", "evasion", "fraud", "irs"],
            "Tax evasion (26 U.S.C. 7201): felony, up to $250K fine and 5 years prison. "
            "Civil fraud penalty: 75% of underpayment (IRC 6663). Failure to file: up to "
            "$25K fine and 1 year prison.",
        ),
        (
            ["offshore", "overseas", "foreign", "fbar", "fatca"],
            "FBAR penalties: up to $100K or 50% of account balance per violation. "
            "FATCA non-compliance: 30% withholding on US-source payments. "
            "Willful violations may trigger criminal prosecution.",
        ),
        (
            ["transfer", "pricing", "corporate"],
            "Transfer pricing violations (IRC 482): IRS can reallocate income between "
            "related entities. Penalties: 20-40% of underpayment for substantial or gross "
            "valuation misstatements.",
        ),
    ]
    query_lower = query.lower()
    results = []
    for keywords, text in knowledge:
        if any(keyword in query_lower for keyword in keywords):
            results.append(text)
    return "\n\n".join(results) if results else "No specific tax law matches found."


@tool
def search_compliance_law(query: str) -> str:
    """Search regulatory compliance knowledge base for applicable frameworks.

    Args:
        query: Natural language query about regulatory compliance.
    """
    knowledge = [
        (
            ["sec", "sox", "reporting", "regulation", "compliance"],
            "SOX 906: false certification can lead to fines up to $5M and 20 years prison. "
            "SOX 802: record destruction can lead to up to 20 years prison. "
            "SEC can impose officer and director bars.",
        ),
        (
            ["aml", "money laundering", "kyc", "sanctions"],
            "AML failures can trigger regulatory fines, monitorships, reporting obligations, "
            "and potential criminal exposure depending on willfulness and scale.",
        ),
        (
            ["fcpa", "bribery", "corruption", "foreign"],
            "FCPA anti-bribery violations can lead to large corporate fines, individual criminal "
            "liability, and books-and-records enforcement for reporting issuers.",
        ),
    ]
    query_lower = query.lower()
    results = []
    for keywords, text in knowledge:
        if any(keyword in query_lower for keyword in keywords):
            results.append(text)
    return "\n\n".join(results) if results else "No specific compliance matches found."


@tool
def search_privacy_law(query: str) -> str:
    """Search privacy law knowledge base for data protection obligations.

    Args:
        query: Natural language query about privacy, GDPR, or data protection.
    """
    knowledge = [
        (
            ["privacy", "gdpr", "consent", "personal data", "user data"],
            "GDPR violations can trigger fines up to EUR 20M or 4% of global annual revenue. "
            "Core principles include lawful basis, purpose limitation, data minimisation, and "
            "data subject rights such as access, deletion, and portability.",
        ),
        (
            ["breach", "leak", "incident", "notification", "security"],
            "Data breaches may require regulator notification within 72 hours under GDPR Art. 33, "
            "plus notice to affected individuals when risk is high. Weak security controls can "
            "also trigger FTC and state-law enforcement.",
        ),
        (
            ["ccpa", "california", "consumer", "sale", "sharing"],
            "CCPA/CPRA provides rights to know, delete, and opt out of sale or sharing of personal "
            "information. Some breach scenarios can create private right of action exposure.",
        ),
    ]
    query_lower = query.lower()
    results = []
    for keywords, text in knowledge:
        if any(keyword in query_lower for keyword in keywords):
            results.append(text)
    return "\n\n".join(results) if results else "No specific privacy law matches found."


# ---------------------------------------------------------------------------
# State definition
# ---------------------------------------------------------------------------


def _last_wins(left: str, right: str) -> str:
    """Reducer: keep the most recently written value."""
    return right if right else left


class LegalState(TypedDict):
    question: str
    law_analysis: str
    needs_tax: bool
    needs_compliance: bool
    needs_privacy: bool
    tax_result: Annotated[str, _last_wins]
    compliance_result: Annotated[str, _last_wins]
    privacy_result: Annotated[str, _last_wins]
    final_answer: str


# ---------------------------------------------------------------------------
# Node implementations
# ---------------------------------------------------------------------------


async def analyze_law(state: LegalState) -> dict:
    """Lead attorney analyses the legal aspects of the question."""
    print("\n  [Node: analyze_law] Lead attorney analysing legal aspects...")
    llm = get_llm()
    messages = [
        SystemMessage(
            content=(
                "You are a senior corporate litigation attorney specialising in contract law, "
                "tort law, and general business law. Analyse the legal aspects of the question "
                "thoroughly. Keep your analysis under 200 words."
            )
        ),
        HumanMessage(content=state["question"]),
    ]
    result = await llm.ainvoke(messages)
    print(f"  [Node: analyze_law] Done ({len(result.content)} chars)")
    return {"law_analysis": result.content}


def check_routing(state: LegalState) -> dict:
    """Choose which specialist agents are needed based on question keywords."""
    print("\n  [Node: check_routing] Determining which specialists are needed...")
    question_lower = state["question"].lower()

    needs_tax = any(
        keyword in question_lower
        for keyword in ["tax", "irs", "evasion", "offshore", "fbar", "fatca"]
    )
    needs_compliance = any(
        keyword in question_lower
        for keyword in ["compliance", "sec", "regulation", "sox", "aml", "fcpa", "governance"]
    )
    needs_privacy = any(
        keyword in question_lower
        for keyword in ["data", "privacy", "gdpr", "consent", "breach", "leak", "ccpa"]
    )

    print(
        "  [Node: check_routing] "
        f"needs_tax={needs_tax}, needs_compliance={needs_compliance}, needs_privacy={needs_privacy}"
    )
    return {
        "needs_tax": needs_tax,
        "needs_compliance": needs_compliance,
        "needs_privacy": needs_privacy,
    }


def route_to_specialists(state: LegalState) -> list[Send]:
    """Dispatch parallel Send objects to the required specialist nodes."""
    sends: list[Send] = []
    if state.get("needs_tax"):
        sends.append(Send("call_tax_specialist", state))
    if state.get("needs_compliance"):
        sends.append(Send("call_compliance_specialist", state))
    if state.get("needs_privacy"):
        sends.append(Send("call_privacy_specialist", state))
    if not sends:
        sends.append(Send("aggregate", state))
    return sends


async def call_tax_specialist(state: LegalState) -> dict:
    """Tax specialist sub-agent."""
    from langgraph.prebuilt import create_react_agent

    print("\n  [Node: call_tax_specialist] Tax specialist agent starting...")

    tax_prompt = (
        "You are a specialist tax attorney and CPA with expertise in corporate tax law, "
        "IRS enforcement, penalties, FBAR/FATCA requirements, and tax fraud statutes. "
        "Use the search_tax_law tool to ground your analysis. Keep your response under 200 words."
    )
    specialist_question = (
        f"Original question: {state['question']}\n\n"
        f"Lead legal analysis: {state.get('law_analysis', 'N/A')}\n\n"
        "Focus on tax consequences only."
    )

    llm = get_llm()
    agent = create_react_agent(model=llm, tools=[search_tax_law], prompt=tax_prompt)
    result = await agent.ainvoke({"messages": [{"role": "user", "content": specialist_question}]})

    final_msg = result["messages"][-1].content
    print(f"  [Node: call_tax_specialist] Done ({len(final_msg)} chars)")
    return {"tax_result": final_msg}


async def call_compliance_specialist(state: LegalState) -> dict:
    """Compliance specialist sub-agent."""
    from langgraph.prebuilt import create_react_agent

    print("\n  [Node: call_compliance_specialist] Compliance specialist agent starting...")

    compliance_prompt = (
        "You are a senior regulatory compliance officer with expertise in SEC enforcement, "
        "SOX compliance, FTC regulations, FCPA, AML/BSA, and corporate governance. "
        "Use the search_compliance_law tool to ground your analysis. Keep your response under 200 words."
    )
    specialist_question = (
        f"Original question: {state['question']}\n\n"
        f"Lead legal analysis: {state.get('law_analysis', 'N/A')}\n\n"
        "Focus on regulatory compliance consequences only."
    )

    llm = get_llm()
    agent = create_react_agent(model=llm, tools=[search_compliance_law], prompt=compliance_prompt)
    result = await agent.ainvoke({"messages": [{"role": "user", "content": specialist_question}]})

    final_msg = result["messages"][-1].content
    print(f"  [Node: call_compliance_specialist] Done ({len(final_msg)} chars)")
    return {"compliance_result": final_msg}


async def call_privacy_specialist(state: LegalState) -> dict:
    """Privacy specialist sub-agent."""
    from langgraph.prebuilt import create_react_agent

    print("\n  [Node: call_privacy_specialist] Privacy specialist agent starting...")

    privacy_prompt = (
        "You are a privacy and data protection attorney with expertise in GDPR, CCPA/CPRA, "
        "FTC privacy enforcement, breach notification, consent requirements, and personal data "
        "governance. Use the search_privacy_law tool to ground your analysis. Keep your response "
        "under 200 words."
    )
    specialist_question = (
        f"Original question: {state['question']}\n\n"
        f"Lead legal analysis: {state.get('law_analysis', 'N/A')}\n\n"
        "Focus on privacy and data protection consequences only."
    )

    llm = get_llm()
    agent = create_react_agent(model=llm, tools=[search_privacy_law], prompt=privacy_prompt)
    result = await agent.ainvoke({"messages": [{"role": "user", "content": specialist_question}]})

    final_msg = result["messages"][-1].content
    print(f"  [Node: call_privacy_specialist] Done ({len(final_msg)} chars)")
    return {"privacy_result": final_msg}


async def aggregate(state: LegalState) -> dict:
    """Combine all specialist analyses into one final answer."""
    print("\n  [Node: aggregate] Combining all specialist analyses...")
    llm = get_llm()

    sections: list[str] = []
    if state.get("law_analysis"):
        sections.append(f"## Legal Analysis\n{state['law_analysis']}")
    if state.get("tax_result"):
        sections.append(f"## Tax Analysis\n{state['tax_result']}")
    if state.get("compliance_result"):
        sections.append(f"## Regulatory Compliance Analysis\n{state['compliance_result']}")
    if state.get("privacy_result"):
        sections.append(f"## Privacy Analysis\n{state['privacy_result']}")

    combined = "\n\n---\n\n".join(sections)
    messages = [
        SystemMessage(
            content=(
                "You are a senior legal counsel synthesising specialist analyses into a "
                "comprehensive, well-structured response. Combine the analyses into a cohesive "
                "answer with clear sections. Avoid redundancy. Keep your response under 500 words."
            )
        ),
        HumanMessage(content=combined),
    ]
    result = await llm.ainvoke(messages)
    print(f"  [Node: aggregate] Done ({len(result.content)} chars)")
    return {"final_answer": result.content}


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------


def create_graph():
    """Build and compile the multi-agent StateGraph."""
    graph = StateGraph(LegalState)

    graph.add_node("analyze_law", analyze_law)
    graph.add_node("check_routing", check_routing)
    graph.add_node("call_tax_specialist", call_tax_specialist)
    graph.add_node("call_compliance_specialist", call_compliance_specialist)
    graph.add_node("call_privacy_specialist", call_privacy_specialist)
    graph.add_node("aggregate", aggregate)

    graph.set_entry_point("analyze_law")
    graph.add_edge("analyze_law", "check_routing")
    graph.add_conditional_edges(
        "check_routing",
        route_to_specialists,
        ["call_tax_specialist", "call_compliance_specialist", "call_privacy_specialist", "aggregate"],
    )
    graph.add_edge("call_tax_specialist", "aggregate")
    graph.add_edge("call_compliance_specialist", "aggregate")
    graph.add_edge("call_privacy_specialist", "aggregate")
    graph.add_edge("aggregate", END)

    return graph.compile()


QUESTION = (
    "If a fintech company leaks customer data without consent, avoids taxes on overseas revenue, "
    "and faces SEC compliance scrutiny, what are the legal, privacy, tax, and regulatory consequences?"
)


async def main():
    print("=" * 70)
    print("STAGE 4: Multi-Agent System (In-Process)")
    print("=" * 70)
    print()
    print("[How it works]")
    print("  1. Lead attorney agent analyses the question")
    print("  2. Keyword router decides which specialist agents are needed")
    print("  3. Tax + Compliance + Privacy specialists run IN PARALLEL (LangGraph Send API)")
    print("  4. Aggregator combines all analyses into a final answer")
    print()
    print("[Graph topology]")
    print("  analyze_law -> check_routing -> [tax + compliance + privacy] -> aggregate -> END")
    print()
    print(f"Question: {QUESTION}")
    print("-" * 70)

    graph = create_graph()
    result = await graph.ainvoke(
        {
            "question": QUESTION,
            "law_analysis": "",
            "needs_tax": False,
            "needs_compliance": False,
            "needs_privacy": False,
            "tax_result": "",
            "compliance_result": "",
            "privacy_result": "",
            "final_answer": "",
        }
    )

    print("\n" + "=" * 70)
    print("FINAL ANSWER")
    print("=" * 70)
    print(result["final_answer"])

    print()
    print("-" * 70)
    print("[Improvements over Stage 3]")
    print("  + Specialisation: each agent has domain-specific expertise")
    print("  + Parallel execution: tax + compliance + privacy agents run concurrently")
    print("  + Better quality: specialist prompts produce deeper analysis")
    print("  + Structured flow: explicit graph topology with conditional routing")
    print()
    print("[Stage 4 (Monolith) vs Stage 5 (Distributed A2A)]")
    print("  +---------------------------+-------------------------------+")
    print("  | Stage 4 (In-Process)      | Stage 5 (A2A Protocol)        |")
    print("  +---------------------------+-------------------------------+")
    print("  | Single process            | Multiple services (ports)     |")
    print("  | Direct function calls     | HTTP-based A2A protocol       |")
    print("  | Shared memory             | Message passing               |")
    print("  | Simple deployment         | Independent scaling           |")
    print("  | Tight coupling            | Loose coupling                |")
    print("  | Easy to debug             | Service discovery + registry  |")
    print("  | Good for small teams      | Good for large organisations  |")
    print("  +---------------------------+-------------------------------+")
    print()
    print("Stage 5 takes this same graph topology and deploys each agent as an A2A service.")
    print("=" * 70)


if __name__ == "__main__":
    load_dotenv()
    asyncio.run(main())
