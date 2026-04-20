"""AgentCore Runtime entry point for the AWS Platform Agent.

Serves the Strands agent via the AG-UI protocol on POST /invocations and /ws.
Usage:
    agentcore dev          # Local development
    agentcore launch       # Deploy to AgentCore Runtime
"""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncIterator
from typing import Any

from ag_ui.core import (
    EventType,
    RunAgentInput,
    RunFinishedEvent,
    RunStartedEvent,
    TextMessageContentEvent,
    TextMessageEndEvent,
    TextMessageStartEvent,
)
from bedrock_agentcore.runtime import serve_ag_ui

from .agent import create_agent
from .drivers import create_driver, list_sources


def _build_agent() -> Any:
    """Create the Platform Agent with Bedrock credentials from the environment."""
    profile_name = os.environ.get("AWS_PROFILE")
    region = os.environ.get("AWS_REGION", "us-east-1")
    return create_agent(profile_name=profile_name, region=region)


# Create agent at module level so it persists across requests
_agent = _build_agent()


async def handler(run_input: RunAgentInput) -> AsyncIterator:
    """AG-UI handler — converts Strands agent responses to AG-UI events.

    Extracts the last user message from the AG-UI thread, runs it through
    the Strands agent, and streams back text events.
    """
    run_id = run_input.run_id
    message_id = str(uuid.uuid4())

    # Extract last user message
    user_prompt = ""
    for msg in reversed(run_input.messages):
        if msg.role == "user":
            if hasattr(msg, "content") and msg.content:
                parts = []
                for part in msg.content:
                    if hasattr(part, "text"):
                        parts.append(part.text)
                user_prompt = " ".join(parts)
            break

    if not user_prompt:
        user_prompt = "Hello"

    # Auto-connect if DB env vars are set and no session exists
    db_host = os.environ.get("DB_HOST")
    if db_host:
        driver_type = os.environ.get("DB_DRIVER_TYPE", "postgresql")
        db_name = os.environ.get("DB_NAME", "db")
        source_id = f"{driver_type}_{db_name}"
        if source_id not in list_sources():
            create_driver(
                driver_type=driver_type,
                source_id=source_id,
                host=db_host,
                port=int(os.environ.get("DB_PORT", "5432")),
                database=db_name,
                user=os.environ.get("DB_USER", ""),
                password=os.environ.get("DB_PASSWORD", ""),
            )
            user_prompt = (
                f"The database is connected with source_id='{source_id}'. "
                f"Use scan_metadata to discover the schema first, then answer: {user_prompt}"
            )

    # Emit run started
    yield RunStartedEvent(type=EventType.RUN_STARTED, thread_id=run_input.thread_id, run_id=run_id)

    # Emit message start
    yield TextMessageStartEvent(
        type=EventType.TEXT_MESSAGE_START,
        message_id=message_id,
        role="assistant",
    )

    # Stream agent response
    try:
        async for event in _agent.stream_async(user_prompt):
            # Extract text from stream events
            if hasattr(event, "data"):
                text = ""
                if isinstance(event.data, str):
                    text = event.data
                elif isinstance(event.data, dict) and "text" in event.data:
                    text = event.data["text"]

                if text:
                    yield TextMessageContentEvent(
                        type=EventType.TEXT_MESSAGE_CONTENT,
                        message_id=message_id,
                        delta=text,
                    )
    except Exception as e:
        yield TextMessageContentEvent(
            type=EventType.TEXT_MESSAGE_CONTENT,
            message_id=message_id,
            delta=f"\n\nError: {e}",
        )

    # Emit message end
    yield TextMessageEndEvent(
        type=EventType.TEXT_MESSAGE_END,
        message_id=message_id,
    )

    # Emit run finished
    yield RunFinishedEvent(type=EventType.RUN_FINISHED, thread_id=run_input.thread_id, run_id=run_id)


def main() -> None:
    """Entry point for AgentCore Runtime."""
    port = int(os.environ.get("PORT", "8080"))
    serve_ag_ui(handler, port=port)


if __name__ == "__main__":
    main()
