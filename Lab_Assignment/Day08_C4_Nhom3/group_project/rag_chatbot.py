"""Reusable workflow layer for the RAG chatbot products."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from src.task4_chunking_indexing import CHUNKS_INDEX_PATH, ensure_index
from src.task9_retrieval_pipeline import retrieve
from group_project.supervisor_workers import SupervisorWorkersPipeline


@dataclass
class ChatTurn:
    """A compact chat-history item used for follow-up questions."""

    role: str
    content: str


class RAGChatbot:
    """Chatbot facade backed by a Supervisor - Workers RAG workflow."""

    def __init__(self):
        self.chunks = ensure_index()
        self.supervisor = SupervisorWorkersPipeline()

    def refresh_index(self) -> dict[str, int]:
        """Reload or rebuild the local chunk index."""
        self.chunks = ensure_index()
        return self.stats()

    def stats(self) -> dict[str, int]:
        """Return corpus statistics for the UI."""
        sources = {
            chunk.get("metadata", {}).get("source", "unknown")
            for chunk in self.chunks
        }
        legal = [
            chunk
            for chunk in self.chunks
            if chunk.get("metadata", {}).get("type") == "legal"
        ]
        news = [
            chunk
            for chunk in self.chunks
            if chunk.get("metadata", {}).get("type") == "news"
        ]
        return {
            "chunks": len(self.chunks),
            "documents": len(sources),
            "legal_chunks": len(legal),
            "news_chunks": len(news),
        }

    def contextualize_query(
        self,
        question: str,
        history: list[dict[str, Any]] | None = None,
    ) -> str:
        """Add short recent chat history so follow-up questions stay grounded."""
        if not history:
            return question

        recent_turns = []
        for turn in history[-4:]:
            role = "Người dùng" if turn.get("role") == "user" else "Trợ lý"
            content = " ".join(str(turn.get("content", "")).split())
            if content:
                recent_turns.append(f"{role}: {content[:500]}")

        if not recent_turns:
            return question

        return (
            f"Câu hỏi hiện tại: {question}\n\n"
            "Ngữ cảnh hội thoại gần nhất:\n"
            + "\n".join(recent_turns)
        )

    def ask(
        self,
        question: str,
        history: list[dict[str, Any]] | None = None,
        top_k: int = 5,
    ) -> dict[str, Any]:
        """Run Supervisor - Workers retrieval + generation with citations."""
        return self.supervisor.run(question, history=history, top_k=top_k)

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        """Expose retrieval-only results for debugging and source review."""
        return retrieve(query, top_k=top_k)


def index_status() -> str:
    """Human-readable index state."""
    if CHUNKS_INDEX_PATH.exists():
        return f"Index: {CHUNKS_INDEX_PATH}"
    return "Index chưa tồn tại"
