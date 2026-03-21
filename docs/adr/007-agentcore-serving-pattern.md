# ADR-007: AgentCore Serving Pattern

**Status**: Accepted

**Date**: 2026-03-21

## Context

The Platform Agent needs a production serving layer for the Bedrock AgentCore Runtime. AgentCore expects agents that speak the AG-UI protocol — an async streaming protocol where the handler receives a `RunAgentInput` and yields AG-UI events (text deltas, tool calls, run lifecycle). Strands Agents SDK uses a different event model (`stream_async` yields Strands-native events). We need to bridge these two protocols.

## Options Considered

1. **Custom AG-UI adapter** — Write a thin `async def handler(RunAgentInput) -> AsyncIterator[AG-UI Event]` that extracts the user prompt, calls `agent.stream_async()`, and maps Strands events to AG-UI events. Straightforward, minimal dependencies.
2. **Wait for native Strands → AG-UI bridge** — The Strands SDK may add a built-in `serve_ag_ui()` wrapper. Would reduce custom code but timeline is uncertain.
3. **Use A2A protocol instead** — Strands supports Agent-to-Agent protocol natively. However, AgentCore Runtime's primary interface is AG-UI, not A2A.

## Decision

Option 1 — custom AG-UI adapter in `src/platform_agent/serve.py`. The adapter:
- Extracts the last user message from `RunAgentInput.messages`
- Auto-connects to the database if `DB_HOST` env var is set
- Streams agent responses as `TextMessageContentEvent` deltas
- Wraps the flow in `RunStartedEvent` / `RunFinishedEvent` lifecycle events

This keeps the serving layer thin (~100 lines) and fully under our control.

## Consequences

- **Positive**: Works today, no dependency on unreleased Strands features. Easy to extend with tool-use events later.
- **Positive**: The agent discovers the schema at runtime — no hardcoded database knowledge.
- **Negative**: Tool call/result events are not yet forwarded to the AG-UI client (they happen inside the Strands agent loop). The client sees only the final text output. This can be enhanced iteratively.
- **Negative**: If Strands ships a native AG-UI bridge, we should evaluate migrating to reduce maintenance.
