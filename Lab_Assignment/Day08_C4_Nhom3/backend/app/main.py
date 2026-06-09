"""FastAPI API for the Vietnamese drug-law RAG chatbot."""

from __future__ import annotations

import sys
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

PROJECT_DIR = Path(__file__).resolve().parents[2]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from group_project.rag_chatbot import RAGChatbot, index_status


class ChatMessage(BaseModel):
    """Conversation item from the web client."""

    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    """Request body for answer generation."""

    question: str = Field(..., min_length=1)
    history: list[ChatMessage] = Field(default_factory=list)
    top_k: int = Field(default=5, ge=1, le=10)


class SearchRequest(BaseModel):
    """Request body for retrieval-only search."""

    query: str = Field(..., min_length=1)
    top_k: int = Field(default=5, ge=1, le=20)


class Source(BaseModel):
    """Retrieved source returned to the frontend."""

    content: str
    score: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)
    source: str | None = None


class WorkerTrace(BaseModel):
    """Supervisor worker execution summary."""

    name: str
    role: str
    status: str
    summary: str
    output: dict[str, Any] = Field(default_factory=dict)


class ChatResponse(BaseModel):
    """Chat answer with citations and source documents."""

    answer: str
    sources: list[Source]
    retrieval_source: str
    contextual_query: str | None = None
    intent: str | None = None
    pipeline: str | None = None
    workers: list[WorkerTrace] = Field(default_factory=list)


class StatsResponse(BaseModel):
    """Corpus/index statistics."""

    chunks: int
    documents: int
    legal_chunks: int
    news_chunks: int
    index_status: str


app = FastAPI(
    title="Drug Law RAG Chatbot API",
    version="1.0.0",
    description="FastAPI backend for a Vietnamese RAG chatbot with citations.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://web:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@lru_cache(maxsize=1)
def get_bot() -> RAGChatbot:
    """Create one RAG workflow instance per API process."""
    return RAGChatbot()


def to_source(item: dict[str, Any]) -> Source:
    """Convert pipeline source dicts to response models."""
    return Source(
        content=str(item.get("content", "")),
        score=float(item.get("score", 0.0)),
        metadata=item.get("metadata", {}) or {},
        source=item.get("source"),
    )


@app.get("/health")
def health() -> dict[str, str]:
    """Health check for Docker and frontend status."""
    return {"status": "ok"}


@app.get("/stats", response_model=StatsResponse)
def stats() -> StatsResponse:
    """Return current corpus/index statistics."""
    bot = get_bot()
    bot_stats = bot.stats()
    return StatsResponse(**bot_stats, index_status=index_status())


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    """Generate an answer using retrieval, reranking, and citation formatting."""
    bot = get_bot()
    history = [
        message.model_dump() if hasattr(message, "model_dump") else message.dict()
        for message in request.history
    ]
    try:
        result = bot.ask(request.question, history=history, top_k=request.top_k)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return ChatResponse(
        answer=result.get("answer", ""),
        sources=[to_source(source) for source in result.get("sources", [])],
        retrieval_source=result.get("retrieval_source", "none"),
        contextual_query=result.get("contextual_query"),
        intent=result.get("intent"),
        pipeline=result.get("pipeline"),
        workers=result.get("workers", []),
    )


@app.post("/search", response_model=list[Source])
def search(request: SearchRequest) -> list[Source]:
    """Return retrieval-only results for debugging and source inspection."""
    bot = get_bot()
    try:
        results = bot.search(request.query, top_k=request.top_k)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return [to_source(item) for item in results]


@app.post("/index/rebuild", response_model=StatsResponse)
def rebuild_index() -> StatsResponse:
    """Refresh the local RAG index and return updated stats."""
    get_bot.cache_clear()
    bot = get_bot()
    bot.refresh_index()
    bot_stats = bot.stats()
    return StatsResponse(**bot_stats, index_status=index_status())
