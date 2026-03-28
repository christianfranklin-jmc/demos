# ADR-012: Multi-Agent Orchestration Pattern

**Status**: Accepted

**Date**: 2026-03-27

## Context

The Snowflake → AWS migration pipeline requires five distinct capabilities: schema extraction, metadata enrichment, data quality enforcement, knowledge graph construction, and natural language querying. A single agent cannot effectively handle all five — each has different tool sets, system prompts, guardrails, and LLM interaction patterns. We need a coordination pattern for multiple specialized agents.

## Options Considered

1. **Single monolithic agent** — One agent with all tools. Simple but the system prompt would be enormous, tool selection accuracy would degrade, and Cedar policies couldn't differentiate capabilities.
2. **Step Functions orchestration** — AWS Step Functions calls each agent in sequence. Clear pipeline semantics, built-in retry/error handling, visual workflow monitoring.
3. **Agent-to-Agent (A2A) protocol** — Agents communicate directly via Strands A2A. More flexible but harder to debug and monitor.

## Decision

**Step Functions orchestration** for the migration pipeline (sequential: Migration → Enrichment → Quality → Mapping → Query). EventBridge triggers for steady-state operations (schema change → re-enrich, quality failure → auto-remediate). Each agent is a separate AgentCore Runtime endpoint with its own Docker container, ECR repository, Memory store, and Cedar policies.

## Consequences

**Positive:**
- Clear pipeline semantics with visual monitoring in Step Functions console
- Each agent has independent scaling, memory, and policy enforcement
- Failure isolation — one agent's error doesn't crash the pipeline
- Cedar policies enforce per-agent guardrails (e.g., Migration Agent is read-only on source)

**Negative:**
- 5 ECR repositories, 5 Runtime endpoints, 5 Memory stores — higher infrastructure cost
- Inter-agent communication is via Step Functions state, not direct message passing
- Cold start latency when agents haven't been invoked recently
