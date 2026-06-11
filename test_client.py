"""End-to-end test client for the Legal Multi-Agent System.

Sends a legal question to the Customer Agent and prints the response.
"""

import asyncio
import os
import sys
from time import perf_counter

import httpx
from dotenv import load_dotenv

load_dotenv()

TARGET_AGENT_URL = os.getenv(
    "TARGET_AGENT_URL",
    os.getenv("CUSTOMER_AGENT_URL", "http://localhost:10100"),
)

QUESTION = (
    "If a company breaks a contract and avoids taxes, "
    "what are the legal and regulatory consequences?"
)


async def main() -> None:
    print(f"Connecting to agent at {TARGET_AGENT_URL}")
    print(f"Question: {QUESTION}")
    print("-" * 60)

    async with httpx.AsyncClient(timeout=300.0) as http_client:
        # Resolve agent card
        card_url = f"{TARGET_AGENT_URL}/.well-known/agent.json"
        try:
            card_resp = await http_client.get(card_url)
            card_resp.raise_for_status()
        except Exception as e:
            print(f"ERROR: Could not reach agent at {card_url}")
            print(f"  {e}")
            print("Make sure all services are running (./start_all.sh)")
            sys.exit(1)

        from a2a.types import AgentCard, Message, Part, Role, TextPart, MessageSendParams
        from a2a.client import A2AClient
        from uuid import uuid4

        agent_card = AgentCard.model_validate(card_resp.json())
        print(f"Connected to agent: {agent_card.name} v{agent_card.version}")
        print("-" * 60)

        # Build the legacy A2AClient
        client = A2AClient(httpx_client=http_client, agent_card=agent_card)

        # Construct the message
        from a2a.types import SendMessageRequest, MessageSendParams as MSP
        message = Message(
            role=Role.user,
            parts=[Part(root=TextPart(text=QUESTION))],
            message_id=str(uuid4()),
        )
        request = SendMessageRequest(
            id=str(uuid4()),
            params=MSP(message=message),
        )

        print("Sending request (this may take 30-60s while agents chain)...\n")
        started_at = perf_counter()
        try:
            response = await client.send_message(request)
        except Exception:
            elapsed = perf_counter() - started_at
            print(f"Elapsed: {elapsed:.2f}s")
            raise
        elapsed = perf_counter() - started_at

        result_text = _extract_response_text(response)

        if result_text:
            print("RESPONSE:")
            print("=" * 60)
            print(result_text)
            print("=" * 60)
            print(f"Elapsed: {elapsed:.2f}s")
        else:
            print("No text response received. Raw response:")
            print(response)
            print(f"Elapsed: {elapsed:.2f}s")


def _extract_response_text(response: object) -> str:
    """Extract text from A2A success, task artifact, message, or failed task status."""
    text = ""
    root = getattr(response, "root", response)
    result = getattr(root, "result", None)
    if result is None:
        return text

    artifacts = getattr(result, "artifacts", None)
    if artifacts:
        for artifact in artifacts:
            for part in getattr(artifact, "parts", []) or []:
                text += _part_text(part)
        if text:
            return text

    parts = getattr(result, "parts", None)
    if parts:
        for part in parts:
            text += _part_text(part)
        if text:
            return text

    status = getattr(result, "status", None)
    status_message = getattr(status, "message", None) if status else None
    if status_message:
        for part in getattr(status_message, "parts", []) or []:
            text += _part_text(part)

    return text


def _part_text(part: object) -> str:
    inner = getattr(part, "root", part)
    return getattr(inner, "text", "") or ""


if __name__ == "__main__":
    asyncio.run(main())
