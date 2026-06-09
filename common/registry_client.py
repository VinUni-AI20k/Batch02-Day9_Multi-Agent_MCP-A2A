"""Registry client helpers.

Provides `discover(task)` to look up an agent endpoint from the registry,
and `register(agent_info)` for agents to self-register on startup.
"""

import asyncio
import logging
import os

import httpx

logger = logging.getLogger(__name__)

REGISTRY_URL = os.getenv("REGISTRY_URL", "http://localhost:10000")

MAX_RETRIES = 3
RETRY_DELAY = 2.0


async def discover(task: str) -> str:
    """Return the endpoint URL of the agent that handles the given task.

    Args:
        task: The task identifier (e.g. "legal_question", "tax_question").

    Returns:
        The HTTP endpoint base URL of the matching agent.

    Raises:
        httpx.HTTPStatusError: If no agent is found after retries.
    """
    last_exc = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{REGISTRY_URL}/discover/{task}")
                resp.raise_for_status()
                endpoint = resp.json()["endpoint"]
                logger.info("[DISCOVER] task=%s → endpoint=%s (attempt %d)", task, endpoint, attempt)
                return endpoint
        except (httpx.HTTPStatusError, httpx.ConnectError) as exc:
            last_exc = exc
            logger.warning("[DISCOVER] task=%s failed (attempt %d/%d): %s", task, attempt, MAX_RETRIES, exc)
            if attempt < MAX_RETRIES:
                await asyncio.sleep(RETRY_DELAY)

    raise last_exc


async def register(agent_info: dict) -> None:
    """Register an agent with the registry.

    Args:
        agent_info: Dict with keys: agent_name, version, description,
                    tasks, endpoint, tags.

    Raises:
        httpx.HTTPStatusError: If registration fails.
    """
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(f"{REGISTRY_URL}/register", json=agent_info)
        resp.raise_for_status()