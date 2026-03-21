# ADR-001: Programming Language

**Status**: Accepted

**Date**: 2026-03-20

## Context

The AWS Platform Agent needs a primary programming language for agent logic, tool implementations, and integration code. The agent will orchestrate LLM calls, database connectivity (via phData Toolkit), dbt transformations, and a Streamlit front-end. The chosen language must have first-class support from the selected agent framework (Strands Agents SDK) and deployment platform (Bedrock AgentCore).

## Options Considered

1. **Python** — Native language for Strands Agents SDK, dbt, Streamlit, and the Bedrock AgentCore SDK. Dominant ecosystem for data engineering and ML.
2. **TypeScript** — Strands has a TypeScript SDK, but dbt and Streamlit are Python-only. Would require a polyglot build and bridging between runtimes.
3. **Java / Kotlin** — Strong AWS SDK support, but no Strands Agents SDK, no dbt integration, and significantly higher development overhead for LLM tooling.

## Decision

Use **Python 3.12+** as the sole programming language.

## Consequences

- **Positive**: Single-language stack across agent, tools, dbt, and Streamlit. No polyglot complexity.
- **Positive**: Largest ecosystem of data engineering libraries. Broad team familiarity.
- **Positive**: Direct compatibility with Strands Agents SDK (`strands-agents`) and Bedrock AgentCore SDK (`bedrock-agentcore`).
- **Negative**: Runtime performance is lower than compiled languages, but irrelevant for an LLM-orchestrated agent where latency is dominated by model inference and database I/O.
- **Negative**: Dependency management requires care (pinned versions via `pyproject.toml`).
