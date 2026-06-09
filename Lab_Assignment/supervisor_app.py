"""Supervisor-Workers RAG Chatbot UI — Day09 Lab Assignment.

Demonstrates the Supervisor → [LegalWorker | NewsWorker] → SynthesisWorker
LangGraph pattern on top of the Day08 RAG pipeline.

Run:
    streamlit run supervisor_app.py

Architecture shown in the UI:
  - Supervisor routes the question to LegalWorker, NewsWorker, or both in parallel.
  - LegalWorker searches legal/upload docs; NewsWorker searches news/upload docs.
  - SynthesisWorker deduplicates and generates the final citation-enriched answer.
"""

from __future__ import annotations

try:
    import streamlit as st
except Exception:
    st = None

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.supervisor_agent import run_supervisor_agent

APP_TITLE = "Supervisor-Workers RAG Chatbot"
APP_SUBTITLE = (
    "LangGraph Supervisor + 3 Workers — Day09 Lab Assignment | "
    "Domain: pháp luật ma túy & tin tức nghệ sĩ Việt Nam"
)

CUSTOM_CSS = """
<style>
:root {
  --primary: #1e3a5f;
  --accent:  #0ea5e9;
  --border:  #e2e8f0;
  --muted:   #64748b;
  --legal-bg:#eff6ff;
  --news-bg: #fef9c3;
  --synth-bg:#f0fdf4;
}
.main .block-container { padding-top: 1.5rem; max-width: 1180px; }
.hero {
  background: linear-gradient(135deg, #0f172a 0%, #1e3a5f 50%, #0ea5e9 130%);
  color: white;
  padding: 22px 26px;
  border-radius: 22px;
  box-shadow: 0 14px 40px rgba(15,23,42,.22);
  margin-bottom: 16px;
}
.hero h1 { margin: 0 0 6px 0; font-size: 1.9rem; }
.hero p  { margin: 0; opacity: .9; font-size: 1rem; }
.badge-row { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 14px; }
.badge {
  display: inline-flex; align-items: center; gap: 5px;
  padding: 6px 10px; border-radius: 999px;
  background: rgba(255,255,255,.13); border: 1px solid rgba(255,255,255,.22);
  font-size: .84rem;
}
.route-box {
  display: flex; align-items: center; gap: 6px; flex-wrap: wrap;
  padding: 10px 14px; border-radius: 14px;
  border: 1px solid var(--border); background: #f8fafc;
  margin: 10px 0;
}
.route-chip {
  padding: 4px 10px; border-radius: 999px; font-size: .83rem; font-weight: 600;
}
.chip-legal  { background: var(--legal-bg); color: #1d4ed8; border: 1px solid #bfdbfe; }
.chip-news   { background: var(--news-bg);  color: #854d0e; border: 1px solid #fde68a; }
.chip-synth  { background: var(--synth-bg); color: #166534; border: 1px solid #bbf7d0; }
.worker-card {
  border: 1px solid var(--border); border-radius: 14px;
  padding: 12px 14px; margin-bottom: 10px; background: #fff;
}
.worker-title { font-weight: 700; font-size: .92rem; margin-bottom: 4px; }
.source-card  {
  border: 1px solid var(--border); border-radius: 12px;
  padding: 12px 14px; background: #fff; margin-bottom: 10px;
}
.source-meta { color: var(--muted); font-size: .84rem; margin-bottom: 6px; }
.metric-card {
  border: 1px solid var(--border); border-radius: 14px;
  padding: 14px 16px; background: white;
  box-shadow: 0 4px 12px rgba(15,23,42,.04);
}
.metric-card .label { color: var(--muted); font-size: .8rem; }
.metric-card .value { font-size: 1.1rem; font-weight: 700; margin-top: 2px; }
</style>
"""


# ─── Helper rendering ──────────────────────────────────────────────────────────

def _route_label(route: list[str]) -> str:
    return " + ".join(route) if route else "unknown"


def render_route_badge(route: list[str], legal_count: int, news_count: int) -> None:
    chips = []
    if "legal" in route:
        chips.append(f'<span class="route-chip chip-legal">LegalWorker ({legal_count} chunks)</span>')
    if "news" in route:
        chips.append(f'<span class="route-chip chip-news">NewsWorker ({news_count} chunks)</span>')
    chips.append(f'<span class="route-chip chip-synth">SynthesisWorker</span>')
    html = (
        '<div class="route-box">'
        '<span style="color:var(--muted);font-size:.82rem;">Route:</span>'
        + " → ".join(chips)
        + "</div>"
    )
    st.markdown(html, unsafe_allow_html=True)


def render_source_cards(sources: list[dict], query: str) -> None:
    if not sources:
        st.info("Không có source documents.")
        return
    import re
    for idx, src in enumerate(sources, 1):
        md = src.get("metadata", {}) or {}
        name = md.get("source") or md.get("path") or f"Source {idx}"
        doc_type = md.get("type", "unknown")
        worker = md.get("worker", "—")
        score = float(src.get("score", 0.0))
        content_snippet = (src.get("content", "") or "")[:600]
        for tok in sorted(set(re.findall(r"\w{3,}", (query or "").lower())), key=len, reverse=True):
            content_snippet = re.sub(f"({re.escape(tok)})", r"**\1**", content_snippet, flags=re.I)
        st.markdown(
            f"""<div class="source-card">
              <div style="font-weight:700;margin-bottom:4px;">#{idx} — {name}</div>
              <div class="source-meta">type: <b>{doc_type}</b> · worker: <b>{worker}</b> · score: <b>{score:.3f}</b></div>
            </div>""",
            unsafe_allow_html=True,
        )
        with st.expander("Snippet", expanded=(idx == 1)):
            st.markdown(content_snippet)
            st.caption(str(md))


def render_header() -> None:
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
    st.markdown(
        f"""<div class="hero">
          <h1>🤖 {APP_TITLE}</h1>
          <p>{APP_SUBTITLE}</p>
          <div class="badge-row">
            <span class="badge">🧭 Supervisor routing</span>
            <span class="badge">⚖️ LegalWorker (legal + upload)</span>
            <span class="badge">📰 NewsWorker (news + upload)</span>
            <span class="badge">🔗 SynthesisWorker</span>
            <span class="badge">⚡ LangGraph Send API</span>
          </div>
        </div>""",
        unsafe_allow_html=True,
    )


def render_arch_metrics() -> None:
    c1, c2, c3, c4 = st.columns(4)
    cards = [
        ("Pattern", "Supervisor + 3 Workers"),
        ("Parallel Dispatch", "LangGraph Send API"),
        ("Corpus", "20 legal · 92 news · 58 upload"),
        ("Generation", "Ollama / Extractive fallback"),
    ]
    for col, (label, value) in zip((c1, c2, c3, c4), cards):
        with col:
            st.markdown(
                f"<div class='metric-card'><div class='label'>{label}</div><div class='value'>{value}</div></div>",
                unsafe_allow_html=True,
            )


def render_sidebar() -> tuple[bool, bool]:
    st.sidebar.markdown("## ⚙️ Settings")
    show_sources = st.sidebar.toggle("Hiển thị source documents", value=True)
    show_route = st.sidebar.toggle("Hiển thị Supervisor route", value=True)

    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🏗️ Agent Architecture")
    st.sidebar.markdown(
        """
```
Supervisor
├── LegalWorker   (legal + upload)
├── NewsWorker    (news  + upload)
└── SynthesisWorker
     ├── dedup chunks
     └── Ollama / Extractive
```
Workers chạy **song song** qua Send API khi cả hai được chọn.
        """
    )

    st.sidebar.markdown("---")
    st.sidebar.markdown("### Gợi ý câu hỏi")
    examples = [
        "Điều 249 quy định hình phạt tàng trữ ma túy như thế nào?",
        "Chi Dân và An Tây bị truy tố tội gì?",
        "Long Nhật và Sơn Ngọc Minh bị bắt như thế nào?",
        "Các hình thức cai nghiện theo Luật 2021?",
        "Miu Lê bị giữ để điều tra tội gì?",
    ]
    for ex in examples:
        if st.sidebar.button(ex, use_container_width=True):
            st.session_state.pending_prompt = ex

    return show_sources, show_route


def render_chat(show_sources: bool, show_route: bool) -> None:
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "last_result" not in st.session_state:
        st.session_state.last_result = None

    chat_tab, sources_tab, arch_tab = st.tabs(["💬 Chat", "📌 Sources", "📐 Architecture"])

    with chat_tab:
        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])
                if msg.get("route") and show_route:
                    render_route_badge(msg["route"], msg.get("legal_count", 0), msg.get("news_count", 0))

        pending = st.session_state.pop("pending_prompt", "") if "pending_prompt" in st.session_state else ""
        prompt = pending or st.chat_input("Hỏi về pháp luật ma túy hoặc tin tức nghệ sĩ...")

        if prompt:
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)

            with st.chat_message("assistant"):
                with st.spinner("Supervisor đang phân tích câu hỏi và điều phối Workers..."):
                    result = run_supervisor_agent(prompt)
                st.markdown(result["answer"])

                if show_route:
                    render_route_badge(result["route"], result["legal_count"], result["news_count"])

                llm_label = result.get("llm", "unknown")
                st.caption(
                    f"LLM: `{llm_label}` · "
                    f"Route: `{_route_label(result['route'])}` · "
                    f"LegalWorker: {result['legal_count']} chunks · "
                    f"NewsWorker: {result['news_count']} chunks"
                )

                if show_sources and result.get("sources"):
                    with st.expander("Nguồn đã sử dụng (SynthesisWorker output)", expanded=False):
                        render_source_cards(result["sources"], prompt)

            st.session_state.last_result = result
            st.session_state.messages.append({
                "role": "assistant",
                "content": result["answer"],
                "route": result["route"],
                "legal_count": result["legal_count"],
                "news_count": result["news_count"],
            })

    with sources_tab:
        st.subheader("Sources từ câu trả lời gần nhất")
        if st.session_state.last_result:
            r = st.session_state.last_result
            st.markdown(
                f"**Route:** `{_route_label(r['route'])}` | "
                f"LegalWorker: **{r['legal_count']}** chunks | "
                f"NewsWorker: **{r['news_count']}** chunks"
            )
            render_source_cards(r.get("sources", []), " ".join(
                m["content"] for m in st.session_state.messages[-4:] if m.get("role") == "user"
            ))
        else:
            st.info("Chưa có câu hỏi nào. Hãy chat trước.")

    with arch_tab:
        st.subheader("Supervisor-Workers Architecture")
        st.markdown(
            """
#### Sơ đồ luồng xử lý

```
User Question
     │
     ▼
┌─────────────────────────────────────────────────────┐
│                    SUPERVISOR NODE                  │
│  Phân tích câu hỏi → keyword routing               │
│  - Từ khoá pháp luật  → route "legal"              │
│  - Từ khoá nghệ sĩ    → route "news"               │
│  - Không rõ ràng      → route "legal" + "news"      │
└──────────────────┬──────────────────────────────────┘
                   │ LangGraph Send API (parallel)
         ┌─────────┴─────────┐
         ▼                   ▼
┌────────────────┐  ┌─────────────────┐
│  LEGAL WORKER  │  │   NEWS WORKER   │
│                │  │                 │
│ Hybrid search  │  │ Hybrid search   │
│ legal+upload   │  │ news+upload     │
│ (Semantic +    │  │ (Semantic +     │
│  BM25 + RRF +  │  │  BM25 + RRF +  │
│  Rerank)       │  │  Rerank)        │
└────────┬───────┘  └────────┬────────┘
         └─────────┬─────────┘
                   ▼
       ┌───────────────────────┐
       │   SYNTHESIS WORKER    │
       │                       │
       │ 1. Gộp chunks         │
       │ 2. Dedup by (src, idx)│
       │ 3. Gọi Ollama hoặc   │
       │    extractive fallback│
       │ 4. Trả về {answer,    │
       │    sources, llm}      │
       └───────────────────────┘
                   │
                   ▼
           Final Answer + Citations
```

#### Workers chi tiết

| Worker | Corpus | Retrieval |
|--------|--------|-----------|
| **LegalWorker** | `type=legal` + `type=upload` | Hybrid (semantic + BM25 + RRF + Rerank) |
| **NewsWorker** | `type=news` + `type=upload` | Hybrid (semantic + BM25 + RRF + Rerank) |
| **SynthesisWorker** | Chunks từ LegalWorker + NewsWorker | Dedup → Ollama (qwen2.5:3b) / Extractive |

#### Corpus thống kê

- **20** chunks `legal` — Bộ luật Hình sự, Luật Phòng chống ma túy 2021, Nghị định
- **92** chunks `news` — Vụ án Chi Dân, An Tây, Miu Lê, Long Nhật, Sơn Ngọc Minh…
- **58** chunks `upload` — Tài liệu người dùng upload
- **170** chunks tổng cộng

#### Lợi ích pattern Supervisor-Workers

1. **Chuyên biệt hoá**: Mỗi worker tập trung vào 1 loại nguồn → giảm nhiễu
2. **Parallel**: LegalWorker + NewsWorker chạy đồng thời → nhanh hơn sequential
3. **Fallback thông minh**: SynthesisWorker dedup và fallback nếu không có chunks
4. **Dễ mở rộng**: Thêm UploadWorker, WebWorker… chỉ cần thêm node + Send
            """
        )


def main() -> None:
    if st is None:
        print("Streamlit not installed. Run: pip install streamlit")
        return

    st.set_page_config(page_title=APP_TITLE, page_icon="🤖", layout="wide")
    render_header()
    render_arch_metrics()
    show_sources, show_route = render_sidebar()
    st.markdown("")
    render_chat(show_sources=show_sources, show_route=show_route)


if __name__ == "__main__":
    main()
