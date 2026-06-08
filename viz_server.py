"""Visualization server for the Legal Multi-Agent System.

- Serves agent_visualization.html on /
- Receives phase events from agents on POST /api/events
- Streams them to browsers on GET /api/events (Server-Sent Events)
- Lists predefined test cases on GET /api/cases
- Triggers a real A2A request to the Customer Agent on POST /api/run

Run with:
    VIZ_SERVER_URL=http://localhost:10200 python -m viz_server

Then point the agents at it via the same VIZ_SERVER_URL env var so they
emit events. Open http://localhost:10200 in a browser.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel

load_dotenv()

logger = logging.getLogger("viz_server")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

ROOT = Path(__file__).resolve().parent
HTML_PATH = ROOT / "agent_visualization.html"

CUSTOMER_AGENT_URL = os.getenv("CUSTOMER_AGENT_URL", "http://localhost:10100")


# ---------------------------------------------------------------------------
# Predefined test cases — exercise different routing branches in law_agent
# ---------------------------------------------------------------------------

TEST_CASES: list[dict[str, str]] = [
    {
        "id": "full",
        "title": "Full pipeline (tax + compliance)",
        "description": "Forces both sub-agents — exercises the parallel Send dispatch.",
        "question": (
            "If a company breaks a contract and avoids taxes, "
            "what are the legal and regulatory consequences?"
        ),
    },
    {
        "id": "compliance_only",
        "title": "Compliance-only branch",
        "description": "SOX whistleblower question — routing should pick compliance, not tax.",
        "question": (
            "What are the SOX whistleblower protections, and how do they affect "
            "internal reporting programs at a public company?"
        ),
    },
    {
        "id": "tax_only",
        "title": "Tax-only branch",
        "description": "Offshore-income reporting — routing should pick tax, not compliance.",
        "question": (
            "What are the IRS penalties for failing to report offshore income "
            "on FBAR filings, and how does the voluntary-disclosure program work?"
        ),
    },
    {
        "id": "law_only",
        "title": "Law-only (no sub-agents)",
        "description": "Pure tort-law question — both routing flags should be false.",
        "question": (
            "What is the legal difference between negligence and gross negligence "
            "in tort law, and how does it affect damages?"
        ),
    },
]


# ---------------------------------------------------------------------------
# SSE fan-out
# ---------------------------------------------------------------------------

class EventBus:
    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue[dict[str, Any]]] = set()
        self._lock = asyncio.Lock()

    async def subscribe(self) -> asyncio.Queue[dict[str, Any]]:
        q: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=256)
        async with self._lock:
            self._subscribers.add(q)
        return q

    async def unsubscribe(self, q: asyncio.Queue[dict[str, Any]]) -> None:
        async with self._lock:
            self._subscribers.discard(q)

    async def publish(self, event: dict[str, Any]) -> None:
        async with self._lock:
            subs = list(self._subscribers)
        for q in subs:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                logger.warning("Dropping event for slow subscriber")


bus = EventBus()


# ---------------------------------------------------------------------------
# A2A trigger
# ---------------------------------------------------------------------------

async def run_a2a_request(question: str, trace_id: str) -> None:
    """Send a question to the Customer Agent and publish a run.* envelope."""
    from a2a.client import A2AClient
    from a2a.types import (
        AgentCard,
        Message,
        MessageSendParams,
        Part,
        Role,
        SendMessageRequest,
        TextPart,
    )

    await bus.publish({
        "agent": "viz",
        "phase": "run.start",
        "trace_id": trace_id,
        "question": question,
        "ts": time.time(),
    })

    try:
        async with httpx.AsyncClient(timeout=300.0) as http_client:
            card_resp = await http_client.get(f"{CUSTOMER_AGENT_URL}/.well-known/agent.json")
            card_resp.raise_for_status()
            agent_card = AgentCard.model_validate(card_resp.json())

            client = A2AClient(httpx_client=http_client, agent_card=agent_card)
            message = Message(
                role=Role.user,
                parts=[Part(root=TextPart(text=question))],
                message_id=str(uuid4()),
                metadata={"trace_id": trace_id},
            )
            request = SendMessageRequest(
                id=str(uuid4()),
                params=MessageSendParams(message=message),
            )
            response = await client.send_message(request)

            result_text = ""
            if hasattr(response, "root"):
                root = response.root
                if hasattr(root, "result"):
                    result = root.result
                    if hasattr(result, "artifacts") and result.artifacts:
                        for artifact in result.artifacts:
                            for part in artifact.parts:
                                p = part.root if hasattr(part, "root") else part
                                if hasattr(p, "text"):
                                    result_text += p.text
                    elif hasattr(result, "parts") and result.parts:
                        for part in result.parts:
                            p = part.root if hasattr(part, "root") else part
                            if hasattr(p, "text"):
                                result_text += p.text

        await bus.publish({
            "agent": "viz",
            "phase": "run.end",
            "trace_id": trace_id,
            "answer": result_text or "(empty response)",
            "ts": time.time(),
        })
    except Exception as exc:
        logger.exception("A2A request failed")
        await bus.publish({
            "agent": "viz",
            "phase": "run.error",
            "trace_id": trace_id,
            "error": str(exc),
            "ts": time.time(),
        })


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("viz_server starting | customer_agent=%s html=%s", CUSTOMER_AGENT_URL, HTML_PATH)
    yield


app = FastAPI(lifespan=lifespan)


@app.get("/")
async def index():
    if not HTML_PATH.exists():
        raise HTTPException(404, "agent_visualization.html not found")
    return FileResponse(HTML_PATH)


@app.get("/api/cases")
async def list_cases():
    return JSONResponse(TEST_CASES)


class RunRequest(BaseModel):
    case_id: str | None = None
    question: str | None = None


@app.post("/api/run")
async def run(req: RunRequest):
    question = req.question
    if req.case_id and not question:
        match = next((c for c in TEST_CASES if c["id"] == req.case_id), None)
        if not match:
            raise HTTPException(400, f"unknown case_id: {req.case_id}")
        question = match["question"]
    if not question:
        raise HTTPException(400, "Provide question or case_id")

    trace_id = str(uuid4())
    asyncio.create_task(run_a2a_request(question, trace_id))
    return {"trace_id": trace_id, "question": question}


@app.post("/api/events")
async def post_event(req: Request):
    """Receive an event from an agent and fan it out to SSE subscribers."""
    try:
        body = await req.json()
    except Exception:
        raise HTTPException(400, "invalid JSON")
    if not isinstance(body, dict) or "agent" not in body or "phase" not in body:
        raise HTTPException(400, "expected {agent, phase, ...}")
    body.setdefault("ts", time.time())
    await bus.publish(body)
    return {"ok": True}


@app.get("/api/events")
async def stream_events(request: Request):
    """SSE stream of agent events."""
    q = await bus.subscribe()

    async def gen():
        try:
            yield "retry: 2000\n\n"
            yield f"event: hello\ndata: {json.dumps({'ts': time.time()})}\n\n"
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(q.get(), timeout=15.0)
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
                    continue
                yield f"data: {json.dumps(event)}\n\n"
        finally:
            await bus.unsubscribe(q)

    return StreamingResponse(gen(), media_type="text/event-stream")


def main() -> None:
    port = int(os.getenv("VIZ_SERVER_PORT", "10200"))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")


if __name__ == "__main__":
    main()
