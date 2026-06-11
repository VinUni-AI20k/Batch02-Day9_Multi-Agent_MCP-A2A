"""FastAPI demo UI for the Day08 Supervisor-Workers assignment."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from .supervisor_workers import SupervisorWorkerAgent

app = FastAPI(title="Day08 Supervisor-Workers Assignment", version="1.0.0")
agent = SupervisorWorkerAgent()


class AskRequest(BaseModel):
    question: str


@app.get("/", response_class=HTMLResponse)
async def index() -> str:
    return HTML


@app.post("/api/ask")
async def ask(payload: AskRequest) -> dict:
    return agent.answer(payload.question).to_dict()


HTML = """<!doctype html>
<html lang="vi">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Supervisor Workers RAG</title>
  <style>
    :root {
      --bg: #f5f3ee;
      --card: #ffffff;
      --ink: #1f2926;
      --muted: #69736f;
      --line: #d7d0c4;
      --accent: #1b7567;
      --accent2: #b96d2d;
      --ok: #16895c;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: var(--bg);
      color: var(--ink);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      letter-spacing: 0;
    }
    main {
      width: min(1240px, 100%);
      margin: 0 auto;
      padding: 20px;
    }
    header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 16px;
      padding-bottom: 16px;
      border-bottom: 1px solid var(--line);
    }
    h1 { margin: 0; font-size: 22px; }
    .sub { color: var(--muted); margin-top: 4px; }
    .grid {
      display: grid;
      grid-template-columns: minmax(0, 1.25fr) minmax(300px, .75fr);
      gap: 18px;
      margin-top: 18px;
    }
    .panel {
      background: var(--card);
      border: 1px solid var(--line);
      border-radius: 8px;
      overflow: hidden;
    }
    .head {
      padding: 13px 15px;
      border-bottom: 1px solid var(--line);
      background: #fbfaf7;
      font-weight: 760;
    }
    .body { padding: 15px; }
    textarea {
      width: 100%;
      min-height: 112px;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 12px;
      resize: vertical;
      font: inherit;
      letter-spacing: 0;
    }
    button {
      margin-top: 10px;
      min-height: 40px;
      border: 0;
      border-radius: 8px;
      padding: 0 15px;
      background: var(--accent);
      color: #fff;
      font-weight: 760;
      cursor: pointer;
    }
    button:disabled { opacity: .7; cursor: wait; }
    .answer {
      white-space: pre-wrap;
      line-height: 1.55;
      min-height: 260px;
    }
    .trace {
      display: grid;
      gap: 9px;
    }
    .event {
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 10px;
      background: #fbfaf7;
    }
    .event strong { color: var(--accent); }
    .sources {
      display: grid;
      gap: 9px;
      margin-top: 12px;
    }
    .source {
      border-left: 3px solid var(--accent2);
      padding-left: 10px;
      color: var(--muted);
      font-size: 13px;
      line-height: 1.45;
    }
    @media (max-width: 860px) {
      .grid { grid-template-columns: 1fr; }
      header { align-items: flex-start; flex-direction: column; }
    }
  </style>
</head>
<body>
<main>
  <header>
    <div>
      <h1>Day08 RAG Agent — Supervisor Workers</h1>
      <div class="sub">Supervisor routes to Legal Worker, News Worker, then Answer Synthesis Worker.</div>
    </div>
  </header>
  <section class="grid">
    <div class="panel">
      <div class="head">Question</div>
      <div class="body">
        <textarea id="question">Hình phạt cho tội tàng trữ trái phép chất ma túy là gì, và có tin tức thực tế liên quan không?</textarea>
        <button id="run">Run Supervisor</button>
      </div>
      <div class="head">Answer</div>
      <div class="body">
        <div class="answer" id="answer">No answer yet.</div>
        <div class="sources" id="sources"></div>
      </div>
    </div>
    <aside class="panel">
      <div class="head">Agent Trace</div>
      <div class="body trace" id="trace">No trace yet.</div>
    </aside>
  </section>
</main>
<script>
  const run = document.getElementById("run");
  const question = document.getElementById("question");
  const answer = document.getElementById("answer");
  const trace = document.getElementById("trace");
  const sources = document.getElementById("sources");

  function escapeHtml(value) {
    return value.replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;");
  }

  run.addEventListener("click", async () => {
    run.disabled = true;
    answer.textContent = "Running supervisor and workers...";
    trace.textContent = "Waiting...";
    sources.textContent = "";
    try {
      const response = await fetch("/api/ask", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({question: question.value})
      });
      const data = await response.json();
      answer.textContent = data.answer;
      trace.innerHTML = data.trace.map(event => `
        <div class="event"><strong>${escapeHtml(event.agent)}</strong><br>${escapeHtml(event.state)} — ${escapeHtml(event.detail)}</div>
      `).join("");
      const allSources = data.worker_results.flatMap(item => item.sources || []);
      sources.innerHTML = allSources.slice(0, 6).map(item => `
        <div class="source"><strong>${escapeHtml(item.source)}</strong> (${escapeHtml(item.domain)}, score ${Number(item.score).toFixed(3)})<br>${escapeHtml(item.content.slice(0, 260))}...</div>
      `).join("");
    } catch (error) {
      answer.textContent = error.message;
    } finally {
      run.disabled = false;
    }
  });
</script>
</body>
</html>
"""
