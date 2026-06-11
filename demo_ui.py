"""Web UI for demonstrating the distributed A2A legal agent system."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from time import perf_counter
from uuid import uuid4

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from common.a2a_client import delegate

load_dotenv()

CUSTOMER_AGENT_URL = os.getenv("CUSTOMER_AGENT_URL", "http://localhost:10100")
REGISTRY_URL = os.getenv("REGISTRY_URL", "http://localhost:10000")

app = FastAPI(title="Legal A2A Demo UI", version="1.0.0")


class AskRequest(BaseModel):
    question: str
    trace_id: str | None = None
    context_id: str | None = None


class AskResponse(BaseModel):
    answer: str
    elapsed_seconds: float
    trace_id: str
    context_id: str


class TraceEvent(BaseModel):
    trace_id: str
    context_id: str
    depth: int
    endpoint: str
    target_agent: str
    state: str
    detail: str = ""
    timestamp: str | None = None


TRACE_EVENTS: dict[str, list[dict]] = {}
MAX_TRACE_EVENTS = 200


@app.get("/", response_class=HTMLResponse)
async def index() -> str:
    return HTML


@app.get("/api/health")
async def health() -> dict:
    async with httpx.AsyncClient(timeout=5.0) as client:
        registry = await _get_json(client, f"{REGISTRY_URL}/health")
        agents = await _get_json(client, f"{REGISTRY_URL}/agents")
        customer_card = await _get_json(
            client, f"{CUSTOMER_AGENT_URL}/.well-known/agent.json"
        )

    return {
        "registry": registry,
        "agents": agents.get("agents", []) if agents else [],
        "customer": customer_card,
        "target": CUSTOMER_AGENT_URL,
    }


@app.post("/api/ask", response_model=AskResponse)
async def ask(payload: AskRequest) -> AskResponse:
    question = payload.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question is required.")

    trace_id = payload.trace_id or str(uuid4())
    context_id = payload.context_id or str(uuid4())
    TRACE_EVENTS[trace_id] = []
    started_at = perf_counter()

    try:
        answer = await delegate(
            endpoint=CUSTOMER_AGENT_URL,
            question=question,
            context_id=context_id,
            trace_id=trace_id,
            depth=0,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    elapsed = perf_counter() - started_at
    if not answer:
        answer = "No response text was returned by the Customer Agent."

    return AskResponse(
        answer=answer,
        elapsed_seconds=elapsed,
        trace_id=trace_id,
        context_id=context_id,
    )


@app.post("/api/trace-events")
async def collect_trace_event(event: TraceEvent) -> dict:
    stored = event.model_dump()
    stored["timestamp"] = stored["timestamp"] or datetime.now(timezone.utc).isoformat()
    events = TRACE_EVENTS.setdefault(event.trace_id, [])
    events.append(stored)
    if len(events) > MAX_TRACE_EVENTS:
        del events[: len(events) - MAX_TRACE_EVENTS]
    return {"status": "ok"}


@app.get("/api/traces/{trace_id}")
async def get_trace_events(trace_id: str) -> dict:
    return {"events": TRACE_EVENTS.get(trace_id, [])}


async def _get_json(client: httpx.AsyncClient, url: str) -> dict:
    try:
        response = await client.get(url)
        response.raise_for_status()
        return response.json()
    except Exception:
        return {}


HTML = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Legal A2A Console</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f6f4ef;
      --surface: #ffffff;
      --surface-2: #fbfaf7;
      --ink: #1f2a27;
      --muted: #6d756f;
      --line: #d9d5cb;
      --accent: #1f7a6b;
      --accent-2: #c7742f;
      --ok: #168a5b;
      --warn: #bd6a1f;
      --bad: #b94a48;
      --shadow: 0 10px 28px rgba(51, 45, 34, 0.10);
    }

    * { box-sizing: border-box; }

    body {
      margin: 0;
      min-height: 100vh;
      background: var(--bg);
      color: var(--ink);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      letter-spacing: 0;
    }

    button, textarea { font: inherit; letter-spacing: 0; }

    .shell {
      width: min(1440px, 100%);
      margin: 0 auto;
      padding: 20px;
    }

    .topbar {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      padding: 4px 0 16px;
      border-bottom: 1px solid var(--line);
    }

    .brand {
      display: flex;
      align-items: center;
      gap: 12px;
      min-width: 0;
    }

    .mark {
      width: 38px;
      height: 38px;
      border-radius: 8px;
      display: grid;
      place-items: center;
      background: #173d35;
      color: #fff;
      font-weight: 800;
      flex: 0 0 auto;
    }

    h1 {
      margin: 0;
      font-size: 20px;
      line-height: 1.2;
      font-weight: 760;
    }

    .target {
      color: var(--muted);
      font-size: 13px;
      margin-top: 3px;
      overflow-wrap: anywhere;
    }

    .status-row {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      justify-content: flex-end;
    }

    .chip {
      min-height: 30px;
      padding: 6px 10px;
      border: 1px solid var(--line);
      border-radius: 999px;
      display: inline-flex;
      align-items: center;
      gap: 7px;
      background: var(--surface-2);
      color: var(--muted);
      font-size: 13px;
      white-space: nowrap;
    }

    .dot {
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: var(--warn);
      flex: 0 0 auto;
    }

    .chip.ok .dot { background: var(--ok); }
    .chip.bad .dot { background: var(--bad); }

    .layout {
      display: grid;
      grid-template-columns: minmax(0, 1.45fr) minmax(320px, 0.75fr);
      gap: 20px;
      padding-top: 20px;
      align-items: start;
    }

    .panel {
      background: var(--surface);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: var(--shadow);
      overflow: hidden;
    }

    .panel-head {
      min-height: 52px;
      padding: 14px 16px;
      border-bottom: 1px solid var(--line);
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      background: var(--surface-2);
    }

    .panel-title {
      margin: 0;
      font-size: 15px;
      font-weight: 740;
    }

    .panel-body {
      padding: 16px;
    }

    .question-form {
      display: grid;
      gap: 12px;
    }

    textarea {
      width: 100%;
      min-height: 118px;
      resize: vertical;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
      color: var(--ink);
      padding: 13px 14px;
      line-height: 1.45;
      outline: none;
    }

    textarea:focus {
      border-color: var(--accent);
      box-shadow: 0 0 0 3px rgba(31, 122, 107, 0.14);
    }

    .actions {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      flex-wrap: wrap;
    }

    .btn {
      min-height: 40px;
      border: 0;
      border-radius: 8px;
      padding: 0 16px;
      background: var(--accent);
      color: #fff;
      font-weight: 740;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 9px;
    }

    .btn:disabled {
      opacity: 0.7;
      cursor: wait;
    }

    .btn-secondary {
      background: #efeae0;
      color: var(--ink);
      border: 1px solid var(--line);
    }

    .spinner {
      width: 15px;
      height: 15px;
      border: 2px solid rgba(255, 255, 255, 0.42);
      border-top-color: #fff;
      border-radius: 50%;
      display: none;
      animation: spin 900ms linear infinite;
    }

    .running .spinner { display: inline-block; }

    @keyframes spin { to { transform: rotate(360deg); } }

    .metric-grid {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 10px;
      margin-top: 14px;
    }

    .metric {
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 10px;
      background: var(--surface-2);
      min-width: 0;
    }

    .metric-label {
      display: block;
      color: var(--muted);
      font-size: 12px;
      margin-bottom: 5px;
    }

    .metric-value {
      display: block;
      font-size: 14px;
      font-weight: 720;
      overflow-wrap: anywhere;
    }

    .result {
      min-height: 260px;
      white-space: pre-wrap;
      line-height: 1.55;
      color: var(--ink);
    }

    .result.empty {
      color: var(--muted);
      display: grid;
      place-items: center;
      text-align: center;
      border: 1px dashed var(--line);
      border-radius: 8px;
      background: var(--surface-2);
    }

    .result h2 {
      margin: 20px 0 8px;
      font-size: 16px;
    }

    .result h2:first-child { margin-top: 0; }
    .result p { margin: 0 0 10px; }

    .flow {
      display: grid;
      gap: 10px;
    }

    .agent {
      display: grid;
      grid-template-columns: 42px minmax(0, 1fr);
      gap: 10px;
      align-items: center;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 10px;
      background: var(--surface);
    }

    .agent-icon {
      width: 42px;
      height: 42px;
      border-radius: 8px;
      display: grid;
      place-items: center;
      background: #efeae0;
      color: var(--accent);
      font-weight: 820;
    }

    .agent.active {
      border-color: rgba(31, 122, 107, 0.55);
      box-shadow: 0 0 0 3px rgba(31, 122, 107, 0.12);
    }

    .agent.done .agent-icon {
      background: rgba(22, 138, 91, 0.12);
      color: var(--ok);
    }

    .agent-name {
      font-weight: 740;
      margin-bottom: 3px;
    }

    .agent-role {
      color: var(--muted);
      font-size: 13px;
      line-height: 1.35;
    }

    .trace-box {
      margin-top: 12px;
      border-top: 1px solid var(--line);
      padding-top: 12px;
      display: grid;
      gap: 8px;
      color: var(--muted);
      font-size: 13px;
      overflow-wrap: anywhere;
    }

    .current-call {
      margin-top: 12px;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 10px;
      background: var(--surface-2);
      color: var(--muted);
      font-size: 13px;
      line-height: 1.4;
    }

    .current-call strong {
      color: var(--ink);
      display: block;
      margin-bottom: 4px;
    }

    .event-log {
      max-height: 210px;
      overflow: auto;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 8px;
      background: var(--surface-2);
      display: grid;
      gap: 6px;
    }

    .event {
      display: grid;
      grid-template-columns: 74px minmax(0, 1fr);
      gap: 8px;
      align-items: start;
      font-size: 12px;
      color: var(--muted);
    }

    .event-state {
      color: var(--ink);
      font-weight: 740;
      text-transform: uppercase;
    }

    .error {
      border: 1px solid rgba(185, 74, 72, 0.45);
      background: #fff7f4;
      color: #843633;
      border-radius: 8px;
      padding: 10px 12px;
      display: none;
      line-height: 1.4;
    }

    .error.visible { display: block; }

    @media (max-width: 900px) {
      .shell { padding: 14px; }
      .topbar { align-items: flex-start; flex-direction: column; }
      .status-row { justify-content: flex-start; }
      .layout { grid-template-columns: 1fr; }
      .metric-grid { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <main class="shell">
    <header class="topbar">
      <div class="brand">
        <div class="mark">A2A</div>
        <div>
          <h1>Legal A2A Console</h1>
          <div class="target" id="target">Customer Agent: checking...</div>
        </div>
      </div>
      <div class="status-row" id="statusRow">
        <span class="chip"><span class="dot"></span>Registry</span>
        <span class="chip"><span class="dot"></span>Customer</span>
      </div>
    </header>

    <section class="layout">
      <div class="panel">
        <div class="panel-head">
          <h2 class="panel-title">Client Question</h2>
          <button class="btn btn-secondary" type="button" id="sampleBtn">Sample</button>
        </div>
        <div class="panel-body">
          <form class="question-form" id="askForm">
            <textarea id="question" spellcheck="true">If a company breaks a contract and avoids taxes, what are the legal and regulatory consequences?</textarea>
            <div class="actions">
              <button class="btn" type="submit" id="runBtn">
                <span class="spinner" aria-hidden="true"></span>
                <span id="runLabel">Run Analysis</span>
              </button>
              <div class="error" id="errorBox"></div>
            </div>
          </form>

          <div class="metric-grid">
            <div class="metric">
              <span class="metric-label">Latency</span>
              <span class="metric-value" id="latency">-</span>
            </div>
            <div class="metric">
              <span class="metric-label">Trace ID</span>
              <span class="metric-value" id="traceId">-</span>
            </div>
            <div class="metric">
              <span class="metric-label">Context ID</span>
              <span class="metric-value" id="contextId">-</span>
            </div>
          </div>
        </div>

        <div class="panel-head">
          <h2 class="panel-title">Agent Response</h2>
        </div>
        <div class="panel-body">
          <div class="result empty" id="result">No response yet.</div>
        </div>
      </div>

      <aside class="panel">
        <div class="panel-head">
          <h2 class="panel-title">Distributed Flow</h2>
          <button class="btn btn-secondary" type="button" id="refreshBtn">Refresh</button>
        </div>
        <div class="panel-body">
          <div class="flow" id="flow">
            <div class="agent" data-agent="customer">
              <div class="agent-icon">C</div>
              <div>
                <div class="agent-name">Customer Agent</div>
                <div class="agent-role">Entry point on port 10100</div>
              </div>
            </div>
            <div class="agent" data-agent="law">
              <div class="agent-icon">L</div>
              <div>
                <div class="agent-name">Law Agent</div>
                <div class="agent-role">StateGraph orchestrator on port 10101</div>
              </div>
            </div>
            <div class="agent" data-agent="tax">
              <div class="agent-icon">T</div>
              <div>
                <div class="agent-name">Tax Agent</div>
                <div class="agent-role">Tax specialist on port 10102</div>
              </div>
            </div>
            <div class="agent" data-agent="compliance">
              <div class="agent-icon">R</div>
              <div>
                <div class="agent-name">Compliance Agent</div>
                <div class="agent-role">Regulatory specialist on port 10103</div>
              </div>
            </div>
          </div>
          <div class="current-call">
            <strong>Current A2A Call</strong>
            <span id="currentCall">Idle</span>
          </div>
          <div class="trace-box">
            <strong>Trace Events</strong>
            <div class="event-log" id="eventLog">No A2A calls yet.</div>
          </div>
          <div class="trace-box" id="agentList">Registry status unavailable.</div>
        </div>
      </aside>
    </section>
  </main>

  <script>
    const form = document.getElementById("askForm");
    const question = document.getElementById("question");
    const runBtn = document.getElementById("runBtn");
    const runLabel = document.getElementById("runLabel");
    const result = document.getElementById("result");
    const latency = document.getElementById("latency");
    const traceId = document.getElementById("traceId");
    const contextId = document.getElementById("contextId");
    const errorBox = document.getElementById("errorBox");
    const statusRow = document.getElementById("statusRow");
    const target = document.getElementById("target");
    const agentList = document.getElementById("agentList");
    const sampleBtn = document.getElementById("sampleBtn");
    const refreshBtn = document.getElementById("refreshBtn");
    const flowNodes = Array.from(document.querySelectorAll(".agent"));
    const currentCall = document.getElementById("currentCall");
    const eventLog = document.getElementById("eventLog");
    let tracePollTimer = null;
    let seenEventCount = 0;

    const sampleQuestion = "If a company breaks a contract and avoids taxes, what are the legal and regulatory consequences?";

    function escapeHtml(value) {
      return value
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;");
    }

    function renderAnswer(text) {
      const safe = escapeHtml(text.trim());
      const lines = safe.split(/\n+/);
      const html = [];
      for (const line of lines) {
        if (line.startsWith("## ")) {
          html.push(`<h2>${line.slice(3)}</h2>`);
        } else if (line.startsWith("# ")) {
          html.push(`<h2>${line.slice(2)}</h2>`);
        } else {
          html.push(`<p>${line}</p>`);
        }
      }
      return html.join("");
    }

    function setRunning(running) {
      runBtn.disabled = running;
      runBtn.classList.toggle("running", running);
      runLabel.textContent = running ? "Running" : "Run Analysis";
      if (running) {
        currentCall.textContent = "Waiting for first A2A call...";
        eventLog.textContent = "Waiting for trace events...";
        seenEventCount = 0;
        flowNodes.forEach((node) => {
          node.classList.remove("active", "done");
        });
      } else {
        flowNodes.forEach((node) => node.classList.remove("active"));
      }
    }

    function setError(message) {
      errorBox.textContent = message || "";
      errorBox.classList.toggle("visible", Boolean(message));
    }

    async function loadHealth() {
      try {
        const response = await fetch("/api/health");
        const data = await response.json();
        const agents = data.agents || [];
        const names = new Set(agents.map((agent) => agent.agent_name));
        target.textContent = `Customer Agent: ${data.target || "http://localhost:10100"}`;
        statusRow.innerHTML = [
          ["Registry", data.registry && data.registry.status === "ok"],
          ["Customer", Boolean(data.customer && data.customer.name)],
          ["Law", names.has("law-agent")],
          ["Tax", names.has("tax-agent")],
          ["Compliance", names.has("compliance-agent")]
        ].map(([label, ok]) => `<span class="chip ${ok ? "ok" : "bad"}"><span class="dot"></span>${label}</span>`).join("");

        if (agents.length) {
          agentList.innerHTML = agents
            .map((agent) => `<div><strong>${escapeHtml(agent.agent_name)}</strong> ${escapeHtml(agent.endpoint || "")}</div>`)
            .join("");
        } else {
          agentList.textContent = "Registry is reachable, but no agents are registered.";
        }
      } catch (error) {
        statusRow.innerHTML = `<span class="chip bad"><span class="dot"></span>Services offline</span>`;
        agentList.textContent = "Start Stage 5 services with ./start_all.sh.";
      }
    }

    function createId() {
      if (window.crypto && window.crypto.randomUUID) {
        return window.crypto.randomUUID();
      }
      return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
    }

    function agentKey(name) {
      const value = String(name || "").toLowerCase();
      if (value.includes("customer")) return "customer";
      if (value.includes("law")) return "law";
      if (value.includes("tax")) return "tax";
      if (value.includes("compliance")) return "compliance";
      return "";
    }

    function updateFlow(events) {
      for (const event of events) {
        const key = agentKey(event.target_agent);
        const node = key ? document.querySelector(`[data-agent="${key}"]`) : null;
        if (!node) continue;
        if (event.state === "calling") {
          flowNodes.forEach((item) => item.classList.remove("active"));
          node.classList.add("active");
          currentCall.textContent = `${event.target_agent} via ${event.endpoint}`;
        }
        if (event.state === "completed") {
          node.classList.remove("active");
          node.classList.add("done");
          currentCall.textContent = `${event.target_agent} completed`;
        }
        if (event.state === "failed") {
          node.classList.remove("active");
          currentCall.textContent = `${event.target_agent} failed`;
        }
      }
    }

    function renderEvents(events) {
      if (!events.length) {
        eventLog.textContent = "No A2A calls yet.";
        return;
      }
      eventLog.innerHTML = events
        .slice()
        .reverse()
        .map((event) => {
          const time = event.timestamp ? new Date(event.timestamp).toLocaleTimeString() : "";
          return `
            <div class="event">
              <div class="event-state">${escapeHtml(event.state || "")}</div>
              <div>
                <div>${escapeHtml(event.target_agent || event.endpoint || "")}</div>
                <div>${escapeHtml(time)} · depth ${escapeHtml(String(event.depth ?? ""))}</div>
              </div>
            </div>`;
        })
        .join("");
    }

    async function refreshTrace(trace) {
      const response = await fetch(`/api/traces/${encodeURIComponent(trace)}`);
      const data = await response.json();
      const events = data.events || [];
      if (events.length !== seenEventCount) {
        seenEventCount = events.length;
        updateFlow(events);
        renderEvents(events);
      }
    }

    function startTracePolling(trace) {
      stopTracePolling();
      tracePollTimer = window.setInterval(() => {
        refreshTrace(trace).catch(() => {});
      }, 700);
    }

    function stopTracePolling() {
      if (tracePollTimer) {
        window.clearInterval(tracePollTimer);
        tracePollTimer = null;
      }
    }

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const requestTraceId = createId();
      const requestContextId = createId();
      setError("");
      setRunning(true);
      result.className = "result empty";
      result.textContent = "Waiting for distributed agent response...";
      latency.textContent = "-";
      traceId.textContent = requestTraceId;
      contextId.textContent = requestContextId;
      startTracePolling(requestTraceId);

      try {
        const response = await fetch("/api/ask", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            question: question.value,
            trace_id: requestTraceId,
            context_id: requestContextId
          })
        });
        const data = await response.json();
        if (!response.ok) {
          throw new Error(data.detail || "Request failed.");
        }
        result.className = "result";
        result.innerHTML = renderAnswer(data.answer || "");
        latency.textContent = `${data.elapsed_seconds.toFixed(2)}s`;
        traceId.textContent = data.trace_id;
        contextId.textContent = data.context_id;
        await refreshTrace(data.trace_id);
        await loadHealth();
      } catch (error) {
        setError(error.message);
        result.className = "result empty";
        result.textContent = "Request failed.";
      } finally {
        await refreshTrace(requestTraceId).catch(() => {});
        stopTracePolling();
        setRunning(false);
      }
    });

    sampleBtn.addEventListener("click", () => {
      question.value = sampleQuestion;
      question.focus();
    });

    refreshBtn.addEventListener("click", loadHealth);
    loadHealth();
  </script>
</body>
</html>
"""
