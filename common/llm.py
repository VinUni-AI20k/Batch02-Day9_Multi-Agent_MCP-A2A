"""Shared LLM factory for all agents.

Uses the Gemini API through Google's OpenAI-compatible endpoint, so the
existing LangChain ChatOpenAI integration can stay in place.
"""

import os

from langchain_openai import ChatOpenAI


def get_llm() -> ChatOpenAI:
    """Return a ChatOpenAI client pointed at the Gemini API."""
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key or api_key.strip() in {"your_key_here", "your_gemini_key_here"}:
        raise ValueError(
            "Missing Gemini API key. Set GEMINI_API_KEY in .env "
            "(or GOOGLE_API_KEY in your environment)."
        )

    return ChatOpenAI(
        temperature=0.3,
        model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
        openai_api_key=api_key,
        openai_api_base=os.getenv(
            "GEMINI_API_BASE",
            "https://generativelanguage.googleapis.com/v1beta/openai/",
        ),
    )
