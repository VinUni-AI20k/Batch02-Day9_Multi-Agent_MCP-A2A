"""Fire-and-forget telemetry helper for the viz_server.

Each agent calls `viz.emit(agent=..., phase=..., trace_id=..., **meta)` at key
phase boundaries. If VIZ_SERVER_URL is not set, calls are no-ops, so agents
run unchanged when the visualization server isn't running.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_VIZ_URL = os.getenv("VIZ_SERVER_URL", "").rstrip("/")
_TIMEOUT = httpx.Timeout(2.0, connect=1.0)


async def _post(payload: dict[str, Any]) -> None:
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            await client.post(f"{_VIZ_URL}/api/events", json=payload)
    except Exception as exc:
        logger.debug("viz.emit failed (non-fatal): %s", exc)


def emit(agent: str, phase: str, trace_id: str | None = None, **meta: Any) -> None:
    """Fire-and-forget event emission. Safe to call from sync or async code.

    Args:
        agent: Logical name (customer, law, tax, compliance, registry).
        phase: Phase identifier (e.g. "start", "discover", "delegate",
            "analyze", "routing", "dispatch", "aggregate", "return").
        trace_id: Request trace_id for correlation.
        **meta: Extra fields (e.g. depth, target, question_preview).
    """
    if not _VIZ_URL:
        return

    payload: dict[str, Any] = {"agent": agent, "phase": phase}
    if trace_id:
        payload["trace_id"] = trace_id
    payload.update(meta)

    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_post(payload))
    except RuntimeError:
        # No running loop — run the post inline. Rare path.
        try:
            asyncio.run(_post(payload))
        except Exception:
            pass
