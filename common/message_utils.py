"""Helpers for normalising LangChain message content into plain text."""

from __future__ import annotations

from typing import Any


def content_to_text(content: Any) -> str:
    """Flatten provider-specific message content into a plain string."""
    if content is None:
        return ""

    if isinstance(content, str):
        return content

    if isinstance(content, list):
        parts = [content_to_text(item) for item in content]
        return "\n".join(part for part in parts if part).strip()

    if isinstance(content, dict):
        text = content.get("text")
        if isinstance(text, str):
            return text

        if "content" in content:
            return content_to_text(content["content"])

        values = [content_to_text(value) for value in content.values()]
        return "\n".join(value for value in values if value).strip()

    return str(content)
