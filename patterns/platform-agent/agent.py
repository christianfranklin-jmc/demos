"""AgentCore Runtime entry point for the Platform Agent (FAST pattern).

Uses BedrockAgentCoreApp with @app.entrypoint to handle requests.
Integrates AgentCoreMemorySessionManager for conversation persistence
and MCP client for Gateway tool discovery.

Usage:
    opentelemetry-instrument python -m agent   # With OTel
    python -m agent                             # Without OTel
"""

from __future__ import annotations

import logging
import os
from typing import Any
from uuid import uuid4

from bedrock_agentcore.runtime import BedrockAgentCoreApp, RequestContext
from prompts.system import SYSTEM_PROMPT
from strands import Agent
from strands.models import BedrockModel
from tools.dbt_generate import generate_dbt_project
from tools.semantic_layer import generate_semantic_layer

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = BedrockAgentCoreApp()

# Direct tools (CPU-bound, filesystem access needed — stay in container)
DIRECT_TOOLS = [generate_dbt_project, generate_semantic_layer]


# ---------------------------------------------------------------------------
# Memory integration
# ---------------------------------------------------------------------------

def _create_memory_manager(session_id: str, user_id: str) -> Any | None:
    """Create an AgentCoreMemorySessionManager if MEMORY_ID is configured."""
    memory_id = os.environ.get("MEMORY_ID") or os.environ.get("AGENTCORE_MEMORY_ID")
    if not memory_id:
        logger.info("MEMORY_ID not set — running without conversation memory")
        return None

    try:
        from strands.agent.session_manager import (
            AgentCoreMemoryConfig,
            AgentCoreMemorySessionManager,
        )

        config = AgentCoreMemoryConfig(
            memory_id=memory_id,
            session_id=session_id,
            actor_id=user_id,
        )
        return AgentCoreMemorySessionManager(
            agentcore_memory_config=config,
            region_name=os.environ.get("AWS_REGION", "us-east-1"),
        )
    except ImportError:
        logger.warning("AgentCoreMemorySessionManager not available — skipping memory")
        return None


# ---------------------------------------------------------------------------
# Gateway MCP tool discovery
# ---------------------------------------------------------------------------

async def _get_gateway_tools() -> list:
    """Discover tools from the AgentCore Gateway via MCP client.

    Returns Strands-compatible tool functions discovered from the Gateway.
    If Gateway is not configured, returns an empty list.
    """
    gateway_url = os.environ.get("GATEWAY_URL")
    if not gateway_url:
        logger.info("GATEWAY_URL not set — running without Gateway tools")
        return []

    try:
        from mcp import ClientSession
        from mcp.client.streamable_http import streamablehttp_client

        # Get OAuth2 token for M2M auth
        from utils.auth import get_gateway_access_token

        token = get_gateway_access_token()
        headers = {"Authorization": f"Bearer {token}"}

        async with streamablehttp_client(gateway_url, headers=headers) as (
            read_stream,
            write_stream,
            _,
        ), ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            tools_result = await session.list_tools()
            logger.info(
                "Discovered %d Gateway tools: %s",
                len(tools_result.tools),
                [t.name for t in tools_result.tools],
            )
            # TODO: Wrap MCP tools as Strands-compatible tool functions
            # For now, return empty — tools are called via agent's native MCP support
            return []
    except Exception:
        logger.exception("Failed to discover Gateway tools")
        return []


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

def _extract_user_id(context: RequestContext) -> str:
    """Extract user ID from JWT claims in the request context."""
    try:
        # RequestContext may provide auth claims differently per version
        if hasattr(context, "authorizer"):
            claims = context.authorizer.get("claims", {})
            return claims.get("sub", "anonymous")
    except (AttributeError, TypeError):
        pass
    return "anonymous"


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

@app.entrypoint
async def invocations(payload: dict, context: RequestContext):
    """Handle incoming agent requests.

    Extracts user message, sets up memory and tools, and streams
    the agent response as events.
    """
    user_id = _extract_user_id(context)
    session_id = payload.get("runtimeSessionId", str(uuid4()))
    prompt = payload.get("prompt", "")

    if not prompt:
        # Try AG-UI format
        messages = payload.get("messages", [])
        for msg in reversed(messages):
            if msg.get("role") == "user":
                content = msg.get("content", [])
                parts = []
                for part in content:
                    if isinstance(part, dict) and "text" in part:
                        parts.append(part["text"])
                    elif isinstance(part, str):
                        parts.append(part)
                prompt = " ".join(parts)
                break

    if not prompt:
        prompt = "Hello"

    logger.info("user=%s session=%s prompt_len=%d", user_id, session_id, len(prompt))

    # Set up memory
    memory_mgr = _create_memory_manager(session_id, user_id)

    # Discover gateway tools
    gateway_tools = []
    try:
        gateway_tools = await _get_gateway_tools()
    except Exception:
        logger.exception("Gateway tool discovery failed — continuing without")

    # Build agent
    region = os.environ.get("AWS_REGION", "us-east-1")
    model = BedrockModel(
        model_id=os.environ.get(
            "BEDROCK_MODEL_ID", "us.anthropic.claude-sonnet-4-20250514-v1:0"
        ),
        region_name=region,
        temperature=0.1,
    )

    agent_kwargs: dict[str, Any] = {
        "model": model,
        "system_prompt": SYSTEM_PROMPT,
        "tools": DIRECT_TOOLS + gateway_tools,
    }
    if memory_mgr:
        agent_kwargs["session_manager"] = memory_mgr

    agent = Agent(**agent_kwargs)

    # Auto-connect to DB if env vars are set and this is first message
    db_host = os.environ.get("DB_HOST")
    if db_host and "connected" not in prompt.lower():
        driver_type = os.environ.get("DB_DRIVER_TYPE", "postgresql")
        db_name = os.environ.get("DB_NAME", "db")
        prompt = (
            f"The database is auto-connected: driver_type={driver_type}, "
            f"database={db_name}. Use scan_metadata to discover the schema "
            f"first, then answer: {prompt}"
        )

    # Stream response
    async for event in agent.stream_async(prompt):
        yield event


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    app.run(port=port)
