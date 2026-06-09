"""Tax Agent LangGraph definition.

Uses create_react_agent with a tax-specialised system prompt.
No tools — it answers purely from LLM knowledge.
"""

from __future__ import annotations

from langgraph.prebuilt import create_react_agent

from common.llm import get_llm

TAX_SYSTEM_PROMPT = """You are a specialist tax attorney and CPA. Answer concisely.

Expertise: corporate tax law, tax evasion/avoidance, IRS enforcement, penalties (IRC §§ 6651/6662/6663), FBAR/FATCA, transfer pricing (IRC § 482), tax fraud (18 U.S.C. § 7201-7207), corporate tax liability, voluntary disclosure.

Be precise about: civil vs criminal penalties, statute of limitations, government agencies involved, company vs individual liability.

Keep your response under 200 words. Note this is for educational purposes only.
"""


def create_graph():
    """Return a compiled LangGraph create_react_agent for tax questions."""
    llm = get_llm()
    graph = create_react_agent(
        model=llm,
        tools=[],
        prompt=TAX_SYSTEM_PROMPT,
    )
    return graph