"""Shared LLM factory for all agents.

Priority order:
  1. USE_OLLAMA=1 in env → Ollama local via OpenAI-compatible endpoint
  2. OPENROUTER_API_KEY present → OpenRouter cloud
  3. Default → Ollama local (fallback when no API key)
"""

import os

from langchain_openai import ChatOpenAI


def get_llm() -> ChatOpenAI:
    """Return a ChatOpenAI-compatible LLM client.

    Set USE_OLLAMA=1 to force local Ollama (useful when OpenRouter quota is exhausted).
    """
    use_ollama = os.getenv("USE_OLLAMA", "0") == "1"
    api_key = os.getenv("OPENROUTER_API_KEY", "")

    if use_ollama or not api_key:
        ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")
        model = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")
        max_tokens = int(os.getenv("LLM_MAX_TOKENS", "600"))
        return ChatOpenAI(
            model=model,
            openai_api_key="ollama",
            openai_api_base=f"{ollama_url}/v1",
            max_tokens=max_tokens,
        )

    return ChatOpenAI(
        model=os.getenv("OPENROUTER_MODEL", "anthropic/claude-sonnet-4-5"),
        openai_api_key=api_key,
        openai_api_base="https://openrouter.ai/api/v1",
    )


def content_to_str(raw) -> str:
    """Normalize LLM message content to plain text.

    Some models (e.g. google/gemma via OpenRouter) return content as
    list[dict] instead of a plain string:
        [{"type": "text", "text": "..."}]
    Calling .strip() or passing such a list to TextPart(text=...) would crash.
    """
    if isinstance(raw, str):
        return raw
    if isinstance(raw, list):
        return "".join(
            block.get("text", "") if isinstance(block, dict) else str(block)
            for block in raw
        )
    return str(raw) if raw is not None else ""