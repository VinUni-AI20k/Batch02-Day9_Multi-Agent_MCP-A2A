"""Registry client helpers.

Provides `discover(task)` to look up an agent endpoint from the registry,
and `register(agent_info)` for agents to self-register on startup.
"""

import asyncio
import os

import httpx

REGISTRY_URL = os.getenv("REGISTRY_URL", "http://localhost:10000")


async def discover(task: str, attempts: int = 3, delay: float = 0.5) -> str:
    """Return the endpoint URL of the agent that handles the given task.

    Args:
        task: The task identifier (e.g. "legal_question", "tax_question").

    Returns:
        The HTTP endpoint base URL of the matching agent.

    Raises:
        httpx.HTTPStatusError: If no agent is found or the registry is unreachable.
    """
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{REGISTRY_URL}/discover/{task}")
                resp.raise_for_status()
                return resp.json()["endpoint"]
        except Exception as exc:
            last_error = exc
            if attempt == attempts:
                break
            await asyncio.sleep(delay * attempt)
    raise last_error or RuntimeError(f"Could not discover task '{task}'")


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
