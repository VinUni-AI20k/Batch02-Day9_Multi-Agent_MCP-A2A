"""Supervisor-workers upgrade for the Day08 drug-law RAG agent.

The original Day08 chatbot called one RAG pipeline directly. This version adds
a supervisor that decides which workers should run, then combines worker
outputs into one cited answer.
"""

from __future__ import annotations

import math
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from time import perf_counter
from typing import Iterable

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

load_dotenv()

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data" / "standardized"
DEFAULT_TOP_K = 4


@dataclass(frozen=True)
class DocumentChunk:
    content: str
    source: str
    domain: str
    score: float = 0.0


@dataclass(frozen=True)
class SupervisorDecision:
    selected_workers: list[str]
    reason: str


@dataclass
class WorkerResult:
    worker: str
    summary: str
    sources: list[DocumentChunk]
    elapsed_seconds: float
    status: str = "ok"


@dataclass
class SupervisorResult:
    question: str
    decision: SupervisorDecision
    worker_results: list[WorkerResult]
    answer: str
    elapsed_seconds: float
    trace: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "question": self.question,
            "decision": {
                "selected_workers": self.decision.selected_workers,
                "reason": self.decision.reason,
            },
            "worker_results": [
                {
                    "worker": item.worker,
                    "summary": item.summary,
                    "elapsed_seconds": item.elapsed_seconds,
                    "status": item.status,
                    "sources": [
                        {
                            "source": source.source,
                            "domain": source.domain,
                            "score": source.score,
                            "content": source.content,
                        }
                        for source in item.sources
                    ],
                }
                for item in self.worker_results
            ],
            "answer": self.answer,
            "elapsed_seconds": self.elapsed_seconds,
            "trace": self.trace,
        }


class CorpusIndex:
    """Small local lexical index over Day08 standardized Markdown documents."""

    def __init__(self, data_dir: Path = DATA_DIR) -> None:
        self.data_dir = data_dir
        self.chunks = self._load_chunks()
        self.idf = self._build_idf(self.chunks)

    def search(self, query: str, *, domain: str, top_k: int = DEFAULT_TOP_K) -> list[DocumentChunk]:
        query_terms = tokenize(query)
        candidates = [chunk for chunk in self.chunks if chunk.domain == domain]
        scored: list[DocumentChunk] = []

        for chunk in candidates:
            score = self._score(query_terms, chunk.content)
            if score > 0:
                scored.append(
                    DocumentChunk(
                        content=chunk.content,
                        source=chunk.source,
                        domain=chunk.domain,
                        score=score,
                    )
                )

        scored.sort(key=lambda item: item.score, reverse=True)
        return scored[:top_k]

    def _load_chunks(self) -> list[DocumentChunk]:
        chunks: list[DocumentChunk] = []
        for domain in ("legal", "news"):
            for path in sorted((self.data_dir / domain).glob("*.md")):
                text = path.read_text(encoding="utf-8")
                for part in chunk_text(text):
                    chunks.append(
                        DocumentChunk(
                            content=part,
                            source=path.name,
                            domain=domain,
                        )
                    )
        return chunks

    @staticmethod
    def _build_idf(chunks: Iterable[DocumentChunk]) -> dict[str, float]:
        docs = list(chunks)
        doc_count = max(len(docs), 1)
        document_frequency: dict[str, int] = {}

        for chunk in docs:
            for term in set(tokenize(chunk.content)):
                document_frequency[term] = document_frequency.get(term, 0) + 1

        return {
            term: math.log((doc_count + 1) / (frequency + 1)) + 1
            for term, frequency in document_frequency.items()
        }

    def _score(self, query_terms: list[str], content: str) -> float:
        terms = tokenize(content)
        if not query_terms or not terms:
            return 0.0

        term_counts: dict[str, int] = {}
        for term in terms:
            term_counts[term] = term_counts.get(term, 0) + 1

        length_norm = math.sqrt(len(terms))
        score = 0.0
        for term in query_terms:
            score += (term_counts.get(term, 0) * self.idf.get(term, 1.0)) / length_norm
        return score


class Supervisor:
    """Routes each user question to the minimum useful worker set."""

    legal_keywords = {
        "luật",
        "điều",
        "nghị",
        "nghị định",
        "định",
        "bộ",
        "bộ luật",
        "hình",
        "phạt",
        "hình phạt",
        "xử",
        "xử phạt",
        "trách",
        "nhiệm",
        "trách nhiệm",
        "cai",
        "nghiện",
        "cai nghiện",
        "ma",
        "túy",
        "tuý",
        "ma túy",
        "ma tuý",
        "tàng",
        "trữ",
        "tàng trữ",
        "mua",
        "bán",
        "mua bán",
        "vận",
        "chuyển",
        "vận chuyển",
    }
    news_keywords = {
        "tin",
        "tức",
        "báo",
        "nghệ",
        "sĩ",
        "nghệ sĩ",
        "vụ",
        "việc",
        "vụ việc",
        "thực",
        "tế",
        "thực tế",
        "ai",
        "năm",
        "bắt",
        "sự kiện",
    }

    def decide(self, question: str) -> SupervisorDecision:
        terms = set(tokenize(question))
        selected: list[str] = []

        if terms & self.legal_keywords:
            selected.append("legal_retrieval_worker")
        if terms & self.news_keywords:
            selected.append("news_retrieval_worker")

        if not selected:
            selected = ["legal_retrieval_worker", "news_retrieval_worker"]

        selected.append("answer_synthesis_worker")
        reason = (
            "Supervisor selected workers by matching legal/news intent keywords "
            "and always finishes with answer synthesis."
        )
        return SupervisorDecision(selected_workers=selected, reason=reason)


class LegalRetrievalWorker:
    name = "legal_retrieval_worker"

    def __init__(self, index: CorpusIndex) -> None:
        self.index = index

    def run(self, question: str) -> WorkerResult:
        started_at = perf_counter()
        sources = self.index.search(question, domain="legal")
        summary = summarize_sources(sources, "Legal Worker")
        return WorkerResult(
            worker=self.name,
            summary=summary,
            sources=sources,
            elapsed_seconds=perf_counter() - started_at,
        )


class NewsRetrievalWorker:
    name = "news_retrieval_worker"

    def __init__(self, index: CorpusIndex) -> None:
        self.index = index

    def run(self, question: str) -> WorkerResult:
        started_at = perf_counter()
        sources = self.index.search(question, domain="news")
        summary = summarize_sources(sources, "News Worker")
        return WorkerResult(
            worker=self.name,
            summary=summary,
            sources=sources,
            elapsed_seconds=perf_counter() - started_at,
        )


class AnswerSynthesisWorker:
    name = "answer_synthesis_worker"

    def run(self, question: str, worker_results: list[WorkerResult]) -> WorkerResult:
        started_at = perf_counter()
        sources = merge_sources(worker_results)
        answer = synthesize_answer(question, sources)
        return WorkerResult(
            worker=self.name,
            summary=answer,
            sources=sources,
            elapsed_seconds=perf_counter() - started_at,
        )


class SupervisorWorkerAgent:
    """End-to-end Day08 agent improved with Supervisor-Workers."""

    def __init__(self) -> None:
        self.index = CorpusIndex()
        self.supervisor = Supervisor()
        self.legal_worker = LegalRetrievalWorker(self.index)
        self.news_worker = NewsRetrievalWorker(self.index)
        self.synthesis_worker = AnswerSynthesisWorker()

    def answer(self, question: str) -> SupervisorResult:
        started_at = perf_counter()
        decision = self.supervisor.decide(question)
        trace = [
            {
                "agent": "supervisor",
                "state": "completed",
                "detail": decision.reason,
            }
        ]

        retrieval_workers = []
        if "legal_retrieval_worker" in decision.selected_workers:
            retrieval_workers.append(self.legal_worker)
        if "news_retrieval_worker" in decision.selected_workers:
            retrieval_workers.append(self.news_worker)

        worker_results: list[WorkerResult] = []
        with ThreadPoolExecutor(max_workers=max(len(retrieval_workers), 1)) as executor:
            futures = {executor.submit(worker.run, question): worker.name for worker in retrieval_workers}
            for future in as_completed(futures):
                worker_name = futures[future]
                trace.append({"agent": worker_name, "state": "calling", "detail": "retrieving evidence"})
                try:
                    result = future.result()
                except Exception as exc:
                    result = WorkerResult(
                        worker=worker_name,
                        summary=str(exc),
                        sources=[],
                        elapsed_seconds=0.0,
                        status="failed",
                    )
                worker_results.append(result)
                trace.append(
                    {
                        "agent": worker_name,
                        "state": result.status,
                        "detail": f"returned {len(result.sources)} sources",
                    }
                )

        trace.append({"agent": self.synthesis_worker.name, "state": "calling", "detail": "synthesizing answer"})
        synthesis = self.synthesis_worker.run(question, worker_results)
        worker_results.append(synthesis)
        trace.append(
            {
                "agent": self.synthesis_worker.name,
                "state": "completed",
                "detail": f"answer length {len(synthesis.summary)} chars",
            }
        )

        return SupervisorResult(
            question=question,
            decision=decision,
            worker_results=worker_results,
            answer=synthesis.summary,
            elapsed_seconds=perf_counter() - started_at,
            trace=trace,
        )


def tokenize(text: str) -> list[str]:
    return re.findall(r"[\wÀ-ỹ]+", text.lower(), flags=re.UNICODE)


def chunk_text(text: str, max_chars: int = 900) -> list[str]:
    paragraphs = [item.strip() for item in re.split(r"\n\s*\n", text) if item.strip()]
    chunks: list[str] = []
    current = ""

    for paragraph in paragraphs:
        if len(current) + len(paragraph) + 2 <= max_chars:
            current = f"{current}\n\n{paragraph}".strip()
        else:
            if current:
                chunks.append(current)
            if len(paragraph) <= max_chars:
                current = paragraph
            else:
                for start in range(0, len(paragraph), max_chars):
                    chunks.append(paragraph[start : start + max_chars])
                current = ""

    if current:
        chunks.append(current)
    return chunks


def summarize_sources(sources: list[DocumentChunk], worker_label: str) -> str:
    if not sources:
        return f"{worker_label}: không tìm thấy evidence phù hợp."
    top_sources = ", ".join(source.source for source in sources[:3])
    return f"{worker_label}: tìm thấy {len(sources)} evidence, nổi bật: {top_sources}."


def merge_sources(worker_results: list[WorkerResult]) -> list[DocumentChunk]:
    seen: set[tuple[str, str]] = set()
    merged: list[DocumentChunk] = []
    for result in worker_results:
        for source in result.sources:
            key = (source.source, source.content[:120])
            if key not in seen:
                seen.add(key)
                merged.append(source)
    domain_priority = {"legal": 0, "news": 1}
    merged.sort(key=lambda item: (domain_priority.get(item.domain, 9), -item.score))
    return merged[:8]


def synthesize_answer(question: str, sources: list[DocumentChunk]) -> str:
    if not sources:
        return (
            "Tôi không tìm thấy đủ evidence trong corpus Day08 để trả lời chắc chắn. "
            "Cần bổ sung tài liệu hoặc kiểm tra lại câu hỏi."
        )

    llm_answer = try_gemini_synthesis(question, sources)
    if llm_answer:
        return llm_answer

    lines = [
        "Bản trả lời extractive từ Supervisor-Workers:",
        "",
        f"Câu hỏi: {question}",
        "",
        "Evidence chính:",
    ]
    for index, source in enumerate(sources[:5], 1):
        snippet = " ".join(source.content.split())[:360]
        lines.append(f"{index}. {snippet} [{source.source}]")
    lines.extend(
        [
            "",
            "Kết luận: câu trả lời cần dựa trên các nguồn được liệt kê ở trên; "
            "nếu cần kết luận pháp lý chính thức, hãy kiểm tra trực tiếp văn bản luật gốc.",
        ]
    )
    return "\n".join(lines)


def try_gemini_synthesis(question: str, sources: list[DocumentChunk]) -> str:
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key or api_key.strip() in {"your_key_here", "your_gemini_key_here"}:
        return ""

    context = "\n\n".join(
        f"[{index}] Source: {source.source} | Domain: {source.domain}\n{source.content}"
        for index, source in enumerate(sources[:6], 1)
    )
    llm = ChatOpenAI(
        temperature=0.2,
        model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
        openai_api_key=api_key,
        openai_api_base=os.getenv(
            "GEMINI_API_BASE",
            "https://generativelanguage.googleapis.com/v1beta/openai/",
        ),
    )

    messages = [
        SystemMessage(
            content=(
                "Bạn là Answer Synthesis Worker trong kiến trúc Supervisor-Workers. "
                "Chỉ trả lời dựa trên context được cung cấp, bằng tiếng Việt, "
                "và gắn citation dạng [source file] cho các nhận định chính."
            )
        ),
        HumanMessage(content=f"Question: {question}\n\nContext:\n{context}"),
    ]

    try:
        result = llm.invoke(messages)
        return str(result.content).strip()
    except Exception:
        return ""


def main() -> None:
    question = (
        "Hình phạt cho tội tàng trữ trái phép chất ma túy là gì, "
        "và có tin tức thực tế liên quan không?"
    )
    result = SupervisorWorkerAgent().answer(question)
    print(result.answer)
    print("\nTrace:")
    for event in result.trace:
        print(f"- {event['agent']}: {event['state']} — {event['detail']}")


if __name__ == "__main__":
    main()
