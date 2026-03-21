# ADR-004: Agent Framework

**Status**: Accepted

**Date**: 2026-03-21

## Context

The AWS Platform Agent requires a framework to orchestrate LLM reasoning, tool invocation, and multi-turn conversations. The framework must support function calling (tools), streaming responses, and be deployable to Amazon Bedrock AgentCore. It should be open-source to avoid proprietary lock-in.

## Options Considered

1. **Strands Agents SDK** — Open-source (Apache-2.0), model-driven Python SDK from AWS. Native `BedrockModel` integration, `@tool` decorator for function calling, built-in `serve_ag_ui()` for AgentCore deployment. Model-agnostic design.
2. **LangChain / LangGraph** — Popular open-source framework with broad model support. Heavier abstraction layer, more complex dependency tree, and no native AgentCore integration.
3. **Custom wrappers** — Direct Bedrock Converse API calls with hand-rolled tool dispatch. Maximum control but significant boilerplate for conversation management, streaming, and error handling.
4. **Amazon Bedrock Agents (managed)** — Fully managed agent service. Less flexible: tool definitions are constrained to OpenAPI specs, limited control over reasoning prompts, and harder to iterate during development.

## Decision

Use **Strands Agents SDK** (`strands-agents`) as the agent framework.

## Consequences

- **Positive**: Minimal boilerplate — an agent is a system prompt, a model, and a list of tools. The `@tool` decorator makes it trivial to expose Python functions to the LLM.
- **Positive**: Native Bedrock integration via `BedrockModel` with streaming, tool use, and cross-region inference profiles.
- **Positive**: Direct path to AgentCore deployment via `serve_ag_ui()` one-liner.
- **Positive**: Apache-2.0 license, model-agnostic — not locked into any single LLM provider.
- **Negative**: Smaller community and ecosystem compared to LangChain.
- **Negative**: Fewer pre-built integrations (retrievers, vector stores, etc.) — though this agent primarily needs custom Toolkit tools, not generic integrations.
