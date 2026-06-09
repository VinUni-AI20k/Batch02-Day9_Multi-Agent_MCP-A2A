"""Streamlit RAG chatbot for Vietnamese drug-law and news documents."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from group_project.rag_chatbot import RAGChatbot, index_status


st.set_page_config(
    page_title="RAG Chatbot Pháp luật ma túy",
    layout="wide",
    initial_sidebar_state="expanded",
)


@st.cache_resource(show_spinner=False)
def load_bot() -> RAGChatbot:
    """Load the chatbot once per Streamlit session."""
    return RAGChatbot()


def render_sources(sources: list[dict]) -> None:
    """Render retrieved sources under an answer."""
    if not sources:
        st.info("Không có nguồn truy xuất.")
        return

    for index, source in enumerate(sources, 1):
        metadata = source.get("metadata", {})
        source_name = metadata.get("source", f"Source {index}")
        doc_type = metadata.get("type", "unknown")
        score = source.get("score", 0.0)
        title = f"{index}. {source_name} | {doc_type} | score {score:.3f}"
        with st.expander(title, expanded=index == 1):
            st.caption(metadata.get("path", ""))
            st.write(source.get("content", "")[:1800])


def render_workers(workers: list[dict]) -> None:
    """Render Supervisor - Workers trace for the last answer."""
    if not workers:
        return

    with st.expander("Supervisor - Workers trace", expanded=False):
        for worker in workers:
            status = worker.get("status", "unknown")
            role = worker.get("role", worker.get("name", "worker"))
            summary = worker.get("summary", "")
            st.markdown(f"**{role}** — `{status}`")
            if summary:
                st.caption(summary)


def reset_chat() -> None:
    """Clear chat history."""
    st.session_state.messages = []


bot = load_bot()

if "messages" not in st.session_state:
    st.session_state.messages = []
if "pending_prompt" not in st.session_state:
    st.session_state.pending_prompt = None

st.title("RAG Chatbot Pháp luật ma túy")

with st.sidebar:
    st.subheader("Pipeline")
    stats = bot.stats()
    col_a, col_b = st.columns(2)
    col_a.metric("Documents", stats["documents"])
    col_b.metric("Chunks", stats["chunks"])
    col_c, col_d = st.columns(2)
    col_c.metric("Legal", stats["legal_chunks"])
    col_d.metric("News", stats["news_chunks"])

    top_k = st.slider("Top K sources", min_value=2, max_value=8, value=5)
    st.caption(index_status())

    if st.button("Rebuild index", use_container_width=True):
        with st.spinner("Đang rebuild index..."):
            bot.refresh_index()
            st.cache_resource.clear()
        st.rerun()

    if st.button("Clear chat", use_container_width=True):
        reset_chat()
        st.rerun()

    st.divider()
    st.markdown(
        "- Pattern: `Supervisor - Workers`\n"
        "- Worker 1: `Query Planner`\n"
        "- Worker 2: `Retrieval`\n"
        "- Worker 3: `Answer + Citation`\n"
        "- Chunking: `SemanticChunker`\n"
        "- Embedding: `BAAI/bge-m3`\n"
        "- Retrieval: `Hybrid BM25 + vector`"
    )

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message["role"] == "assistant":
            render_workers(message.get("workers", []))
            render_sources(message.get("sources", []))

prompt = st.chat_input("Nhập câu hỏi về pháp luật ma túy hoặc bài báo đã crawl")
active_prompt = prompt or st.session_state.pending_prompt
st.session_state.pending_prompt = None

if active_prompt:
    st.session_state.messages.append({"role": "user", "content": active_prompt})
    with st.chat_message("user"):
        st.markdown(active_prompt)

    history = st.session_state.messages[:-1]
    with st.chat_message("assistant"):
        with st.spinner("Đang truy xuất và tạo câu trả lời..."):
            result = bot.ask(active_prompt, history=history, top_k=top_k)
        answer = result.get("answer", "")
        st.markdown(answer)
        render_workers(result.get("workers", []))
        render_sources(result.get("sources", []))

    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": answer,
            "sources": result.get("sources", []),
            "retrieval_source": result.get("retrieval_source", "none"),
            "workers": result.get("workers", []),
            "pipeline": result.get("pipeline", "supervisor_workers"),
        }
    )

if not st.session_state.messages:
    sample_questions = [
        "Luật Phòng chống ma túy quy định những hình thức cai nghiện nào?",
        "Hình phạt cho hành vi tàng trữ trái phép chất ma túy là gì?",
        "Những nghệ sĩ nào trong dữ liệu tin tức liên quan đến ma túy?",
    ]
    st.write("Câu hỏi gợi ý")
    for question in sample_questions:
        if st.button(question, use_container_width=True):
            st.session_state.pending_prompt = question
            st.rerun()
