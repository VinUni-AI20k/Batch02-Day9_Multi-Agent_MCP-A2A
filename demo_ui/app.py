"""Local HTML demo for the distributed agent system."""

from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from common.a2a_client import delegate

load_dotenv()

ROOT_DIR = Path(__file__).resolve().parent
STATIC_DIR = ROOT_DIR / "static"
PROJECT_DIR = ROOT_DIR.parent
LOG_DIR = PROJECT_DIR / ".stage5_logs"

REGISTRY_URL = os.getenv("REGISTRY_URL", "http://localhost:10000")
CUSTOMER_AGENT_URL = os.getenv("CUSTOMER_AGENT_URL", "http://localhost:10100")
LAW_AGENT_URL = os.getenv("LAW_AGENT_URL", "http://localhost:10101")
TAX_AGENT_URL = os.getenv("TAX_AGENT_URL", "http://localhost:10102")
COMPLIANCE_AGENT_URL = os.getenv("COMPLIANCE_AGENT_URL", "http://localhost:10103")


class QuestionRequest(BaseModel):
    question: str


app = FastAPI(title="Legal Multi-Agent Demo UI", version="1.0.0")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


async def fetch_agent_card_status(endpoint: str) -> dict:
    """Return basic availability info for an A2A agent endpoint."""
    tried: list[str] = []
    async with httpx.AsyncClient(timeout=10.0) as client:
        for path in ("/.well-known/agent-card.json", "/.well-known/agent.json"):
            url = f"{endpoint}{path}"
            tried.append(url)
            try:
                resp = await client.get(url)
                if resp.is_success:
                    payload = resp.json()
                    return {
                        "ok": True,
                        "url": endpoint,
                        "name": payload.get("name") or endpoint,
                        "version": payload.get("version") or "unknown",
                        "path": path,
                    }
            except Exception:
                continue

    return {
        "ok": False,
        "url": endpoint,
        "name": endpoint,
        "version": "unknown",
        "path": "",
        "error": f"Could not fetch agent card from: {', '.join(tried)}",
    }


@app.get("/api/status")
async def status() -> dict:
    services = [
        {"label": "Registry", "endpoint": REGISTRY_URL, "type": "registry"},
        {"label": "Customer Agent", "endpoint": CUSTOMER_AGENT_URL, "type": "agent"},
        {"label": "Law Agent", "endpoint": LAW_AGENT_URL, "type": "agent"},
        {"label": "Tax Agent", "endpoint": TAX_AGENT_URL, "type": "agent"},
        {"label": "Compliance Agent", "endpoint": COMPLIANCE_AGENT_URL, "type": "agent"},
    ]

    registry_info: dict = {
        "ok": False,
        "url": REGISTRY_URL,
        "agent_count": 0,
        "agents": [],
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            health = await client.get(f"{REGISTRY_URL}/health")
            health.raise_for_status()
            registry_info.update(health.json())
            registry_info["ok"] = True
        except Exception as exc:
            registry_info["error"] = str(exc)

        try:
            agents_resp = await client.get(f"{REGISTRY_URL}/agents")
            agents_resp.raise_for_status()
            registry_info["agents"] = agents_resp.json().get("agents", [])
        except Exception as exc:
            registry_info["agents_error"] = str(exc)

    service_statuses = []
    for service in services:
        if service["type"] == "registry":
            service_statuses.append(
                {
                    "label": service["label"],
                    "endpoint": service["endpoint"],
                    "ok": registry_info.get("ok", False),
                    "detail": (
                        f"{registry_info.get('agent_count', 0)} agents registered"
                        if registry_info.get("ok")
                        else registry_info.get("error", "Registry unavailable")
                    ),
                }
            )
        else:
            card_status = await fetch_agent_card_status(service["endpoint"])
            service_statuses.append(
                {
                    "label": service["label"],
                    "endpoint": service["endpoint"],
                    "ok": card_status["ok"],
                    "detail": (
                        f"{card_status['name']} v{card_status['version']}"
                        if card_status["ok"]
                        else card_status.get("error", "Agent unavailable")
                    ),
                }
            )

    return {
        "registry": registry_info,
        "services": service_statuses,
    }


@app.get("/api/logs")
async def logs() -> dict:
    files = [
        "registry.err.log",
        "customer.err.log",
        "law.err.log",
        "tax.err.log",
        "compliance.err.log",
        "demo_ui.err.log",
    ]
    payload: dict[str, str] = {}
    for filename in files:
        path = LOG_DIR / filename
        if path.exists():
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
            payload[filename] = "\n".join(lines[-40:])
        else:
            payload[filename] = ""
    return {"logs": payload}


@app.post("/api/ask")
async def ask(request: QuestionRequest) -> dict:
    question = request.question.strip()
    if not question:
        return {"ok": False, "answer": "", "error": "Please enter a question."}

    try:
        answer = await delegate(
            endpoint=CUSTOMER_AGENT_URL,
            question=question,
            context_id=str(uuid4()),
            trace_id=str(uuid4()),
            depth=0,
        )
        if not answer:
            return {
                "ok": False,
                "answer": "",
                "error": "The agent returned an empty response.",
            }
        return {"ok": True, "answer": answer}
    except Exception as exc:
        return {"ok": False, "answer": "", "error": str(exc)}
