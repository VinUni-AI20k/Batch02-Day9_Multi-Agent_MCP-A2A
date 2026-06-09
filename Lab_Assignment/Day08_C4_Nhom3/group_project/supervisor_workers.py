"""Supervisor - Workers pipeline for the group RAG chatbot.

The runtime data source is the chunk index created by Task 4:
`data/indexes/chunks.json`. The supervisor only coordinates workers; workers do
not crawl, convert, or read raw documents during chat-time.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from src.task9_retrieval_pipeline import retrieve
from src.task10_generation import generate_answer_from_chunks


@dataclass
class WorkerReport:
    """Small serializable report for UI/debugging."""

    name: str
    role: str
    status: str
    summary: str
    output: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert report to a JSON-friendly dict."""
        return {
            "name": self.name,
            "role": self.role,
            "status": self.status,
            "summary": self.summary,
            "output": self.output,
        }


class BaseWorker:
    """Base class for pipeline workers."""

    name = "base_worker"
    role = "Base worker"

    def run(self, state: dict[str, Any]) -> WorkerReport:
        raise NotImplementedError


class QueryPlannerWorker(BaseWorker):
    """Normalize the question, preserve short history, and classify intent."""

    name = "query_planner_worker"
    role = "Query planner"

    LEGAL_TERMS = {
        "luật",
        "điều",
        "khoản",
        "nghị định",
        "hình phạt",
        "tàng trữ",
        "sử dụng",
        "mua bán",
        "cai nghiện",
        "ma túy",
        "ma tuý",
    }
    NEWS_TERMS = {
        "nghệ sĩ",
        "ca sĩ",
        "rapper",
        "diễn viên",
        "người mẫu",
        "bị bắt",
        "tin tức",
        "vnexpress",
    }

    def run(self, state: dict[str, Any]) -> WorkerReport:
        question = " ".join(str(state.get("question", "")).split())
        history = state.get("history") or []
        contextual_query = self._contextualize_query(question, history)
        intent = self._classify_intent(contextual_query)

        state["question"] = question
        state["contextual_query"] = contextual_query
        state["intent"] = intent

        return WorkerReport(
            name=self.name,
            role=self.role,
            status="ok",
            summary=f"Chuẩn hóa câu hỏi và phân loại intent: {intent}.",
            output={
                "intent": intent,
                "history_turns_used": min(len(history), 4),
                "contextual_query_chars": len(contextual_query),
            },
        )

    def _contextualize_query(
        self,
        question: str,
        history: list[dict[str, Any]],
    ) -> str:
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

    def _classify_intent(self, text: str) -> str:
        lowered = text.lower()
        legal_hits = sum(1 for term in self.LEGAL_TERMS if term in lowered)
        news_hits = sum(1 for term in self.NEWS_TERMS if term in lowered)

        if legal_hits and news_hits:
            return "mixed_legal_news"
        if news_hits:
            return "news_lookup"
        if legal_hits:
            return "legal_lookup"
        return "general_rag"


class RetrievalWorker(BaseWorker):
    """Retrieve evidence chunks from the Task 4 chunk index."""

    name = "retrieval_worker"
    role = "Evidence retriever"

    def run(self, state: dict[str, Any]) -> WorkerReport:
        query = state.get("contextual_query") or state.get("question", "")
        top_k = int(state.get("top_k", 5))
        sources = retrieve(query, top_k=top_k)

        state["sources"] = sources
        state["retrieval_source"] = (
            sources[0].get("source", "none") if sources else "none"
        )

        top_sources = []
        for source in sources[:3]:
            metadata = source.get("metadata", {})
            top_sources.append(
                {
                    "source": metadata.get("source", "unknown"),
                    "type": metadata.get("type", "unknown"),
                    "score": round(float(source.get("score", 0.0)), 4),
                }
            )

        return WorkerReport(
            name=self.name,
            role=self.role,
            status="ok",
            summary=f"Truy xuất {len(sources)} chunks từ chunks.json.",
            output={
                "retrieval_source": state["retrieval_source"],
                "top_k": top_k,
                "top_sources": top_sources,
            },
        )


class AnswerWorker(BaseWorker):
    """Compose the final cited answer from retrieved chunks."""

    name = "answer_worker"
    role = "Citation answer composer"

    def run(self, state: dict[str, Any]) -> WorkerReport:
        query = state.get("contextual_query") or state.get("question", "")
        sources = state.get("sources") or []
        result = generate_answer_from_chunks(query, sources)

        state["answer"] = result.get("answer", "")
        state["sources"] = result.get("sources", sources)
        state["retrieval_source"] = result.get(
            "retrieval_source",
            state.get("retrieval_source", "none"),
        )

        status = "ok" if state["answer"] else "empty"
        return WorkerReport(
            name=self.name,
            role=self.role,
            status=status,
            summary="Tạo câu trả lời cuối cùng có citation từ evidence chunks.",
            output={
                "answer_chars": len(state["answer"]),
                "sources_used": len(state["sources"]),
            },
        )


class SupervisorWorkersPipeline:
    """Coordinate the RAG workflow using the Supervisor - Workers pattern."""

    pipeline_name = "supervisor_workers"

    def __init__(self, workers: list[BaseWorker] | None = None):
        self.workers = workers or [
            QueryPlannerWorker(),
            RetrievalWorker(),
            AnswerWorker(),
        ]

    def run(
        self,
        question: str,
        history: list[dict[str, Any]] | None = None,
        top_k: int = 5,
    ) -> dict[str, Any]:
        """Run the full supervised worker pipeline."""
        state: dict[str, Any] = {
            "question": question,
            "history": history or [],
            "top_k": top_k,
            "errors": [],
        }
        reports: list[WorkerReport] = []

        for worker in self.workers:
            try:
                reports.append(worker.run(state))
            except Exception as exc:
                state["errors"].append({"worker": worker.name, "error": str(exc)})
                reports.append(
                    WorkerReport(
                        name=worker.name,
                        role=worker.role,
                        status="error",
                        summary=str(exc),
                    )
                )

        answer = state.get("answer") or (
            "Tôi không thể xác minh thông tin này từ nguồn hiện có."
        )

        return {
            "answer": answer,
            "sources": state.get("sources", []),
            "retrieval_source": state.get("retrieval_source", "none"),
            "question": state.get("question", question),
            "contextual_query": state.get("contextual_query", question),
            "intent": state.get("intent", "unknown"),
            "pipeline": self.pipeline_name,
            "workers": [report.to_dict() for report in reports],
            "errors": state.get("errors", []),
        }
