"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";

type Role = "user" | "assistant";

type Source = {
  content: string;
  score: number;
  metadata: {
    source?: string;
    type?: string;
    path?: string;
    chunk_id?: string;
  };
  source?: string | null;
};

type WorkerTrace = {
  name: string;
  role: string;
  status: string;
  summary: string;
};

type ChatMessage = {
  role: Role;
  content: string;
  sources?: Source[];
  retrievalSource?: string;
  pipeline?: string;
  intent?: string;
  workers?: WorkerTrace[];
};

type Stats = {
  chunks: number;
  documents: number;
  legal_chunks: number;
  news_chunks: number;
  index_status: string;
};

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const samples = [
  "Luật Phòng chống ma túy quy định những hình thức cai nghiện nào?",
  "Hình phạt cho hành vi tàng trữ trái phép chất ma túy là gì?",
  "Những nghệ sĩ nào trong dữ liệu tin tức liên quan đến ma túy?"
];

function sourceTitle(source: Source, index: number) {
  const name = source.metadata.source ?? `Source ${index + 1}`;
  const type = source.metadata.type ?? "unknown";
  return `${index + 1}. ${name} · ${type} · ${source.score.toFixed(3)}`;
}

export default function Home() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [topK, setTopK] = useState(5);
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(false);
  const [rebuilding, setRebuilding] = useState(false);
  const [error, setError] = useState("");

  const latestSources = useMemo(() => {
    for (let index = messages.length - 1; index >= 0; index -= 1) {
      const message = messages[index];
      if (message.role === "assistant" && message.sources?.length) {
        return message.sources;
      }
    }
    return [];
  }, [messages]);

  async function loadStats() {
    const response = await fetch(`${API_URL}/stats`, { cache: "no-store" });
    if (!response.ok) {
      throw new Error(`Stats request failed: ${response.status}`);
    }
    setStats(await response.json());
  }

  useEffect(() => {
    loadStats().catch((statsError) => {
      setError(statsError instanceof Error ? statsError.message : "Không tải được stats");
    });
  }, []);

  async function submitQuestion(question: string) {
    const trimmed = question.trim();
    if (!trimmed || loading) {
      return;
    }

    setError("");
    setLoading(true);
    setInput("");

    const nextMessages: ChatMessage[] = [
      ...messages,
      { role: "user", content: trimmed }
    ];
    setMessages(nextMessages);

    try {
      const history = messages.map((message) => ({
        role: message.role,
        content: message.content
      }));
      const response = await fetch(`${API_URL}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: trimmed, history, top_k: topK })
      });

      if (!response.ok) {
        const detail = await response.text();
        throw new Error(detail || `Chat request failed: ${response.status}`);
      }

      const data = await response.json();
      setMessages([
        ...nextMessages,
        {
          role: "assistant",
          content: data.answer,
          sources: data.sources ?? [],
          retrievalSource: data.retrieval_source,
          pipeline: data.pipeline,
          intent: data.intent,
          workers: data.workers ?? []
        }
      ]);
    } catch (chatError) {
      const message =
        chatError instanceof Error ? chatError.message : "Không gọi được API";
      setError(message);
      setMessages([
        ...nextMessages,
        {
          role: "assistant",
          content: `Không xử lý được câu hỏi. ${message}`
        }
      ]);
    } finally {
      setLoading(false);
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await submitQuestion(input);
  }

  async function rebuildIndex() {
    setRebuilding(true);
    setError("");
    try {
      const response = await fetch(`${API_URL}/index/rebuild`, {
        method: "POST"
      });
      if (!response.ok) {
        throw new Error(`Rebuild failed: ${response.status}`);
      }
      setStats(await response.json());
    } catch (rebuildError) {
      setError(
        rebuildError instanceof Error ? rebuildError.message : "Không rebuild được index"
      );
    } finally {
      setRebuilding(false);
    }
  }

  return (
    <main className="shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brandMark">R</div>
          <div>
            <h1>RAG Chatbot</h1>
            <p>Pháp luật ma túy</p>
          </div>
        </div>

        <section className="panel">
          <div className="panelTitle">Corpus</div>
          <div className="metrics">
            <div>
              <span>{stats?.documents ?? "-"}</span>
              <label>docs</label>
            </div>
            <div>
              <span>{stats?.chunks ?? "-"}</span>
              <label>chunks</label>
            </div>
            <div>
              <span>{stats?.legal_chunks ?? "-"}</span>
              <label>legal</label>
            </div>
            <div>
              <span>{stats?.news_chunks ?? "-"}</span>
              <label>news</label>
            </div>
          </div>
        </section>

        <section className="panel">
          <div className="panelTitle">Retrieval</div>
          <label className="sliderLabel" htmlFor="top-k">
            Top K <strong>{topK}</strong>
          </label>
          <input
            id="top-k"
            type="range"
            min="2"
            max="8"
            value={topK}
            onChange={(event) => setTopK(Number(event.target.value))}
          />
          <button className="secondaryButton" onClick={rebuildIndex} disabled={rebuilding}>
            {rebuilding ? "Rebuilding..." : "Rebuild index"}
          </button>
          <button className="ghostButton" onClick={() => setMessages([])}>
            Clear chat
          </button>
        </section>

        <section className="panel stackList">
          <div className="panelTitle">Stack</div>
          <span>Supervisor - Workers</span>
          <span>Query Planner Worker</span>
          <span>Retrieval Worker</span>
          <span>Answer Worker</span>
          <span>SemanticChunker</span>
          <span>BAAI/bge-m3</span>
          <span>Hybrid BM25 + vector</span>
        </section>
      </aside>

      <section className="chatColumn">
        <div className="topbar">
          <div>
            <h2>Hỏi đáp có citation</h2>
            <p>{stats?.index_status ?? "Đang kiểm tra index"}</p>
          </div>
          <div className="statusBadge">{loading ? "Retrieving" : "Ready"}</div>
        </div>

        {error ? <div className="errorBanner">{error}</div> : null}

        <div className="messages">
          {messages.length === 0 ? (
            <div className="emptyState">
              {samples.map((sample) => (
                <button key={sample} onClick={() => submitQuestion(sample)}>
                  {sample}
                </button>
              ))}
            </div>
          ) : (
            messages.map((message, index) => (
              <article className={`message ${message.role}`} key={`${message.role}-${index}`}>
                <div className="messageRole">
                  {message.role === "user" ? "Bạn" : "Trợ lý"}
                  {message.retrievalSource ? (
                    <span>{message.retrievalSource}</span>
                  ) : null}
                  {message.intent ? <span>{message.intent}</span> : null}
                </div>
                <div className="messageText">{message.content}</div>
                {message.workers?.length ? (
                  <div className="workerTrace">
                    {message.workers.map((worker) => (
                      <div className="workerStep" key={worker.name}>
                        <strong>{worker.role}</strong>
                        <span>{worker.status}</span>
                        <p>{worker.summary}</p>
                      </div>
                    ))}
                  </div>
                ) : null}
              </article>
            ))
          )}
        </div>

        <form className="composer" onSubmit={handleSubmit}>
          <input
            value={input}
            onChange={(event) => setInput(event.target.value)}
            placeholder="Nhập câu hỏi..."
            disabled={loading}
          />
          <button type="submit" disabled={loading || !input.trim()}>
            Send
          </button>
        </form>
      </section>

      <aside className="sourcesColumn">
        <div className="sourcesHeader">
          <h2>Sources</h2>
          <span>{latestSources.length}</span>
        </div>

        <div className="sourcesList">
          {latestSources.length === 0 ? (
            <div className="sourceEmpty">Chưa có nguồn.</div>
          ) : (
            latestSources.map((source, index) => (
              <details className="sourceItem" key={`${source.metadata.chunk_id}-${index}`} open={index === 0}>
                <summary>{sourceTitle(source, index)}</summary>
                <p className="sourcePath">{source.metadata.path ?? ""}</p>
                <p>{source.content.slice(0, 1600)}</p>
              </details>
            ))
          )}
        </div>
      </aside>
    </main>
  );
}
