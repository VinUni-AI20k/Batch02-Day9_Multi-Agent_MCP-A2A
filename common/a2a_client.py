"""A2A delegation helper.

Provides `delegate(endpoint, question, context_id, trace_id, depth)` which
sends a message to another A2A agent and returns the text response.
"""

from __future__ import annotations

import asyncio
import logging
import os
from uuid import uuid4

import httpx

from a2a.client import A2AClient
from a2a.types import (
    AgentCard,
    GetTaskRequest,
    Message,
    MessageSendParams,
    Part,
    Role,
    SendMessageRequest,
    TaskQueryParams,
    TaskState,
    TextPart,
)

logger = logging.getLogger(__name__)

TRACE_EVENTS_URL = os.getenv(
    "A2A_TRACE_EVENTS_URL",
    "http://127.0.0.1:8080/api/trace-events",
)

TERMINAL_TASK_STATES = {
    TaskState.completed,
    TaskState.canceled,
    TaskState.failed,
    TaskState.rejected,
}


async def delegate(
    endpoint: str,
    question: str,
    context_id: str,
    trace_id: str,
    depth: int,
) -> str:
    """Send a question to an A2A agent and return the text response.

    Args:
        endpoint: Base URL of the target agent (e.g. "http://localhost:10101").
        question: The question to ask.
        context_id: Current A2A context ID to propagate.
        trace_id: Trace ID generated at the Customer Agent; propagated throughout.
        depth: Current delegation depth (used to enforce MAX_DELEGATION_DEPTH).

    Returns:
        The agent's text response, or an empty string if none could be extracted.
    """
    async with httpx.AsyncClient(timeout=300.0) as http_client:
        target_agent = _agent_name_from_endpoint(endpoint)
        await _emit_trace_event(
            http_client=http_client,
            trace_id=trace_id,
            context_id=context_id,
            depth=depth,
            endpoint=endpoint,
            target_agent=target_agent,
            state="calling",
            detail="A2A request started",
        )

        try:
            # Fetch agent card
            card_url = f"{endpoint}/.well-known/agent.json"
            card_resp = await http_client.get(card_url)
            card_resp.raise_for_status()
            agent_card = AgentCard.model_validate(card_resp.json())

            # Build deprecated (legacy) A2AClient — straightforward for send_message
            client = A2AClient(httpx_client=http_client, agent_card=agent_card)

            # Build message with trace metadata
            message = Message(
                role=Role.user,
                parts=[Part(root=TextPart(text=question))],
                message_id=str(uuid4()),
                context_id=context_id,
                metadata={
                    "trace_id": trace_id,
                    "context_id": context_id,
                    "delegation_depth": depth,
                },
            )

            request = SendMessageRequest(
                id=str(uuid4()),
                params=MessageSendParams(message=message),
            )

            logger.debug(
                "Delegating to %s (depth=%d, trace=%s)", endpoint, depth, trace_id
            )

            response = await client.send_message(request)

            # Extract text from SendMessageResponse. If the task is still running,
            # poll the task store; otherwise a fallback can accidentally read the
            # original user message from task history.
            result = await _extract_text_or_wait(client, response)
            await _emit_trace_event(
                http_client=http_client,
                trace_id=trace_id,
                context_id=context_id,
                depth=depth,
                endpoint=endpoint,
                target_agent=target_agent,
                state="completed",
                detail=f"A2A response returned {len(result)} chars",
            )
            return result
        except Exception as exc:
            await _emit_trace_event(
                http_client=http_client,
                trace_id=trace_id,
                context_id=context_id,
                depth=depth,
                endpoint=endpoint,
                target_agent=target_agent,
                state="failed",
                detail=str(exc),
            )
            raise


async def _extract_text_or_wait(
    client: A2AClient,
    response: object,
    *,
    max_wait_seconds: float = 300.0,
    poll_interval_seconds: float = 1.0,
) -> str:
    """Extract artifact/status text, polling the task until it reaches a final state."""
    result = _result_from_response(response)
    task_id = getattr(result, "id", None)

    text = _extract_text(response)
    if text:
        return text

    if not task_id:
        return ""

    deadline = asyncio.get_running_loop().time() + max_wait_seconds
    while asyncio.get_running_loop().time() < deadline:
        status = getattr(result, "status", None)
        state = getattr(status, "state", None) if status else None
        if state in TERMINAL_TASK_STATES:
            return _extract_text_from_result(result)

        await asyncio.sleep(poll_interval_seconds)
        response = await client.get_task(
            GetTaskRequest(
                id=str(uuid4()),
                params=TaskQueryParams(id=task_id, history_length=0),
            )
        )
        result = _result_from_response(response)
        text = _extract_text(response)
        if text:
            return text

    logger.warning("Timed out waiting for A2A task %s", task_id)
    return _extract_text_from_result(result)


def _result_from_response(response: object) -> object | None:
    """Return the result object inside a JSON-RPC response wrapper."""
    if hasattr(response, "root"):
        response = response.root
    return getattr(response, "result", None)


def _extract_text(response: object) -> str:
    """Extract agent output text from artifacts, direct messages, or status messages."""
    return _extract_text_from_result(_result_from_response(response))


def _extract_text_from_result(result: object | None) -> str:
    """Walk a Task or Message result and collect agent output TextPart.text values."""
    text = ""

    if result is None:
        return text

    # Task — text lives in artifacts
    artifacts = getattr(result, "artifacts", None)
    if artifacts:
        for artifact in artifacts:
            parts = getattr(artifact, "parts", []) or []
            for part in parts:
                text += _part_text(part)
        if text:
            return text

    # Message — text lives in parts directly
    parts = getattr(result, "parts", None)
    if parts:
        for part in parts:
            text += _part_text(part)

    if text:
        return text

    # Failed tasks usually carry the human-readable error in status.message.
    if not text:
        status = getattr(result, "status", None)
        status_message = getattr(status, "message", None) if status else None
        if status_message:
            msg_parts = getattr(status_message, "parts", []) or []
            for part in msg_parts:
                text += _part_text(part)

    return text


def _part_text(part: object) -> str:
    """Extract text from a Part object (handling both Part(root=TextPart) and raw TextPart)."""
    inner = getattr(part, "root", part)
    return getattr(inner, "text", "") or ""


def _agent_name_from_endpoint(endpoint: str) -> str:
    """Return a readable agent name for a local Stage 5 endpoint."""
    if ":10100" in endpoint:
        return "Customer Agent"
    if ":10101" in endpoint:
        return "Law Agent"
    if ":10102" in endpoint:
        return "Tax Agent"
    if ":10103" in endpoint:
        return "Compliance Agent"
    return endpoint


async def _emit_trace_event(
    *,
    http_client: httpx.AsyncClient,
    trace_id: str,
    context_id: str,
    depth: int,
    endpoint: str,
    target_agent: str,
    state: str,
    detail: str,
) -> None:
    """Best-effort event emitter for the demo UI."""
    if not TRACE_EVENTS_URL:
        return

    try:
        await http_client.post(
            TRACE_EVENTS_URL,
            json={
                "trace_id": trace_id,
                "context_id": context_id,
                "depth": depth,
                "endpoint": endpoint,
                "target_agent": target_agent,
                "state": state,
                "detail": detail,
            },
            timeout=1.5,
        )
    except Exception:
        logger.debug("Trace event collector unavailable", exc_info=True)
