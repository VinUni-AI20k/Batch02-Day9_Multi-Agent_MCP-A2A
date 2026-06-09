"""Shared LLM factory for all agents and stage demos.

Prefers Google's Gemini API when a Gemini key is configured, and keeps
OpenRouter as a fallback for older workshop setups.
"""

import os

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI


def _get_temperature() -> float:
    """Return a shared temperature for all providers."""
    return float(os.getenv("LLM_TEMPERATURE", "0.3"))


def _get_gemini_api_key() -> str | None:
    """Return a Gemini API key from standard env vars or migrated configs."""
    for env_var in ("GOOGLE_API_KEY", "GEMINI_API_KEY"):
        value = os.getenv(env_var)
        if value:
            return value

    # Some earlier local setups reused OPENROUTER_API_KEY for a Gemini key.
    migrated_key = os.getenv("OPENROUTER_API_KEY")
    if migrated_key and migrated_key.startswith("AIza"):
        return migrated_key

    return None


def get_llm():
    """Return the chat model configured for this workspace."""
    gemini_api_key = _get_gemini_api_key()
    if gemini_api_key:
        return ChatGoogleGenerativeAI(
            model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite"),
            google_api_key=gemini_api_key,
            temperature=_get_temperature(),
            max_output_tokens=int(
                os.getenv("GEMINI_MAX_OUTPUT_TOKENS", os.getenv("LLM_MAX_TOKENS", "512"))
            ),
            convert_system_message_to_human=True,
        )

    openrouter_api_key = os.getenv("OPENROUTER_API_KEY")
    if openrouter_api_key:
        return ChatOpenAI(
            model=os.getenv("OPENROUTER_MODEL", "anthropic/claude-sonnet-4-5"),
            openai_api_key=openrouter_api_key,
            openai_api_base="https://openrouter.ai/api/v1",
            temperature=_get_temperature(),
            max_tokens=int(
                os.getenv("OPENROUTER_MAX_TOKENS", os.getenv("LLM_MAX_TOKENS", "64"))
            ),
        )

    raise RuntimeError(
        "No LLM API key found. Set GOOGLE_API_KEY for Gemini or OPENROUTER_API_KEY for OpenRouter."
    )
