"""Supervisor-Workers RAG Agent — Day09 Lab Assignment.

Architecture (LangGraph StateGraph):

    ┌──────────────┐
    │  supervisor  │  ← phân tích câu hỏi, quyết định route
    └──────┬───────┘
           │ Send API (parallel)
    ┌──────┴──────────────────┐
    ▼                         ▼
┌──────────────┐   ┌──────────────────┐
│ legal_worker │   │   news_worker    │
│ (legal+upload│   │ (news+upload docs│
│   chunks)    │   │    chunks)       │
└──────┬───────┘   └────────┬─────────┘
       └─────────┬──────────┘
                 ▼
       ┌──────────────────┐
       │ synthesis_worker │  ← dedup + Ollama/fallback generation
       └──────────────────┘

Workers chạy SONG SONG (LangGraph Send API) khi cần cả hai loại nguồn.
Supervisor route chỉ legal_worker nếu hỏi thuần pháp luật,
chỉ news_worker nếu hỏi thuần nghệ sĩ/sự kiện,
hoặc cả hai khi câu hỏi kết hợp.
"""

from __future__ import annotations

import logging
from typing import Annotated, TypedDict

from langgraph.graph import END, StateGraph
from langgraph.types import Send

from .task5_semantic_search import semantic_search
from .task6_lexical_search import lexical_search, normalize_text
from .task7_reranking import rerank, rerank_rrf
from .task10_generation import generate_with_citation

logger = logging.getLogger(__name__)


# ─── Routing keyword sets ──────────────────────────────────────────────────────

LEGAL_KEYWORDS = {
    # Vietnamese
    "điều", "luật", "nghị định", "hình phạt", "tàng trữ", "cai nghiện",
    "bộ luật", "hình sự", "phòng chống", "khung hình", "mức phạt",
    "tội danh", "quy định", "điều khoản", "xử phạt", "truy tố",
    "tố tụng", "vi phạm", "chế tài", "khoản", "điểm", "phạt tù",
    # Accent-folded
    "dieu", "luat", "nghi dinh", "hinh phat", "tang tru", "cai nghien",
    "bo luat", "hinh su", "phong chong", "khung hinh", "muc phat",
    "toi danh", "quy dinh", "xu phat", "truy to", "vi pham", "che tai",
    "phat tu",
}

NEWS_KEYWORDS = {
    # Vietnamese celebrities & crime news
    "nghệ sĩ", "ca sĩ", "chi dân", "an tây", "miu lê", "long nhật",
    "sơn ngọc minh", "trúc phương", "showbiz", "tin tức", "bị bắt",
    "chuyên án", "vụ án", "khởi tố", "tạm giam", "điều tra",
    "bắt quả tang", "ma túy tổng hợp", "dương tính",
    # Accent-folded
    "nghe si", "ca si", "chi dan", "an tay", "miu le", "long nhat",
    "son ngoc minh", "truc phuong", "bi bat", "chuyen an", "vu an",
    "khoi to", "tam giam", "dieu tra", "bat qua tang", "duong tinh",
}


# ─── State definition ──────────────────────────────────────────────────────────

def _keep_nonempty(a: list, b: list) -> list:
    """Reducer: keep whichever list is non-empty (workers write, supervisor inits empty)."""
    return b if b else a


class RAGState(TypedDict):
    question: str
    route: list[str]                                          # e.g. ["legal", "news"]
    legal_chunks: Annotated[list[dict], _keep_nonempty]      # legal_worker output
    news_chunks: Annotated[list[dict], _keep_nonempty]       # news_worker output
    final_answer: str
    sources: list[dict]
    llm: str


# ─── Helper: type-filtered hybrid retrieval ────────────────────────────────────

def _filtered_retrieve(query: str, doc_types: set[str], top_k: int = 6) -> list[dict]:
    """Hybrid search (semantic + BM25 → RRF) filtered to the specified doc types."""
    limit = max(top_k * 4, 20)
    dense = semantic_search(query, top_k=limit)
    sparse = lexical_search(query, top_k=limit)
    merged = rerank_rrf([dense, sparse], top_k=limit)
    filtered = [
        c for c in merged
        if c.get("metadata", {}).get("type", "unknown") in doc_types
    ]
    if not filtered:
        return []
    return rerank(query, filtered, top_k=top_k)


# ─── Nodes ─────────────────────────────────────────────────────────────────────

def supervisor_node(state: RAGState) -> dict:
    """Phân tích câu hỏi và quyết định route đến workers nào.

    Logic:
    - Chứa từ khóa pháp luật   → route "legal"
    - Chứa từ khóa nghệ sĩ/tin → route "news"
    - Không rõ ràng             → route cả "legal" lẫn "news"
    """
    q_norm = normalize_text(state["question"])

    route: list[str] = []
    if any(kw in q_norm for kw in LEGAL_KEYWORDS):
        route.append("legal")
    if any(kw in q_norm for kw in NEWS_KEYWORDS):
        route.append("news")
    if not route:
        route = ["legal", "news"]

    logger.info("Supervisor | question=%r | route=%s", state["question"][:60], route)
    return {
        "route": route,
        "legal_chunks": [],
        "news_chunks": [],
    }


def legal_worker_node(state: RAGState) -> dict:
    """Worker chuyên tìm kiếm trong tài liệu pháp luật (legal + upload).

    Trả về top legal chunks liên quan nhất từ:
    - Bộ luật Hình sự, Luật Phòng chống ma túy, Nghị định
    - Tài liệu người dùng upload (type='upload')
    """
    q = state["question"]
    logger.info("LegalWorker | searching: %r", q[:60])
    chunks = _filtered_retrieve(q, {"legal", "upload"}, top_k=5)
    logger.info("LegalWorker | found %d chunks", len(chunks))
    for c in chunks:
        c.setdefault("metadata", {})["worker"] = "legal"
    return {"legal_chunks": chunks}


def news_worker_node(state: RAGState) -> dict:
    """Worker chuyên tìm kiếm trong tin tức nghệ sĩ (news + upload).

    Trả về top news chunks liên quan nhất từ:
    - Bài báo về vụ án nghệ sĩ (Chi Dân, An Tây, Miu Lê, Long Nhật…)
    - Tài liệu người dùng upload (type='upload')
    """
    q = state["question"]
    logger.info("NewsWorker | searching: %r", q[:60])
    chunks = _filtered_retrieve(q, {"news", "upload"}, top_k=5)
    logger.info("NewsWorker | found %d chunks", len(chunks))
    for c in chunks:
        c.setdefault("metadata", {})["worker"] = "news"
    return {"news_chunks": chunks}


def synthesis_worker_node(state: RAGState) -> dict:
    """Tổng hợp kết quả từ LegalWorker + NewsWorker → tạo câu trả lời có citation.

    - Gộp + dedup chunks từ cả hai workers
    - Gọi Ollama (nếu có) hoặc extractive fallback
    - Trả về câu trả lời cuối cùng
    """
    legal = state.get("legal_chunks") or []
    news = state.get("news_chunks") or []
    all_chunks = legal + news

    # Deduplicate by (source, chunk_index)
    seen: set[tuple] = set()
    unique: list[dict] = []
    for c in all_chunks:
        md = c.get("metadata", {}) or {}
        key = (md.get("source", ""), md.get("chunk_index", -1))
        if key not in seen:
            seen.add(key)
            unique.append(c)

    logger.info(
        "SynthesisWorker | legal=%d news=%d unique=%d",
        len(legal), len(news), len(unique),
    )

    if unique:
        result = generate_with_citation(state["question"], context_chunks=unique)
    else:
        # Fallback: không có worker chunks → chạy full hybrid pipeline
        logger.warning("SynthesisWorker | no worker chunks, falling back to full pipeline")
        result = generate_with_citation(state["question"])

    return {
        "final_answer": result["answer"],
        "sources": result.get("sources", []),
        "llm": result.get("llm", "unknown"),
    }


# ─── Routing function (conditional edges) ─────────────────────────────────────

def route_to_workers(state: RAGState) -> list[Send]:
    """Supervisor quyết định Send message đến workers nào."""
    sends: list[Send] = []
    if "legal" in state["route"]:
        sends.append(Send("legal_worker", state))
    if "news" in state["route"]:
        sends.append(Send("news_worker", state))
    # Nếu supervisor không route được → fallback gửi cả hai
    if not sends:
        sends = [Send("legal_worker", state), Send("news_worker", state)]
    return sends


# ─── Graph construction ────────────────────────────────────────────────────────

def build_graph():
    """Xây dựng và compile StateGraph Supervisor-Workers."""
    graph = StateGraph(RAGState)

    graph.add_node("supervisor", supervisor_node)
    graph.add_node("legal_worker", legal_worker_node)
    graph.add_node("news_worker", news_worker_node)
    graph.add_node("synthesis_worker", synthesis_worker_node)

    graph.set_entry_point("supervisor")
    graph.add_conditional_edges(
        "supervisor",
        route_to_workers,
        ["legal_worker", "news_worker"],
    )
    graph.add_edge("legal_worker", "synthesis_worker")
    graph.add_edge("news_worker", "synthesis_worker")
    graph.add_edge("synthesis_worker", END)

    return graph.compile()


_graph = None


def get_graph():
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph


# ─── Public API ────────────────────────────────────────────────────────────────

def run_supervisor_agent(question: str) -> dict:
    """Chạy Supervisor-Workers RAG agent và trả về kết quả đầy đủ.

    Returns:
        {
            "answer": str,          # câu trả lời cuối cùng
            "sources": list[dict],  # chunks đã dùng để sinh câu trả lời
            "llm": str,             # tên model hoặc "fallback-extractive"
            "route": list[str],     # ["legal"] | ["news"] | ["legal","news"]
            "legal_count": int,     # số chunks từ LegalWorker
            "news_count": int,      # số chunks từ NewsWorker
        }
    """
    result = get_graph().invoke({
        "question": question,
        "route": [],
        "legal_chunks": [],
        "news_chunks": [],
        "final_answer": "",
        "sources": [],
        "llm": "",
    })
    return {
        "answer": result["final_answer"],
        "sources": result.get("sources", []),
        "llm": result.get("llm", "unknown"),
        "route": result.get("route", []),
        "legal_count": len(result.get("legal_chunks", [])),
        "news_count": len(result.get("news_chunks", [])),
    }


if __name__ == "__main__":
    import sys
    q = sys.argv[1] if len(sys.argv) > 1 else "Chi Dân và An Tây bị truy tố tội gì?"
    print(f"\nQuestion: {q}")
    r = run_supervisor_agent(q)
    print(f"Route: {r['route']}")
    print(f"LegalWorker: {r['legal_count']} chunks | NewsWorker: {r['news_count']} chunks")
    print(f"LLM: {r['llm']}")
    print(f"\nAnswer:\n{r['answer']}")
