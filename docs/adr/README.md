# Architecture Decision Records

This directory contains Architecture Decision Records (ADRs) for the AWS Platform Agent project.

## What is an ADR?

An ADR is a short document that captures a significant architectural or technical decision, including the context, options considered, and consequences. When an auditor or new team member asks "Why did you choose X?", the answer lives here.

## Index

| ADR | Title | Status | Date |
|-----|-------|--------|------|
| [001](001-programming-language.md) | Programming Language | Accepted | 2026-03-20 |
| [002](002-llm-provider.md) | LLM Provider | Accepted | 2026-03-20 |
| [003](003-deployment-environment.md) | Deployment Environment | Accepted | 2026-03-20 |
| [004](004-agent-framework.md) | Agent Framework | Accepted | 2026-03-21 |
| [005](005-demo-database.md) | Demo Database | Accepted | 2026-03-21 |
| [006](006-data-connectivity-layer.md) | Data Connectivity Layer | Accepted | 2026-03-21 |
| [007](007-agentcore-serving-pattern.md) | AgentCore Serving Pattern | Accepted | 2026-03-21 |
| [008](008-fast-integration.md) | FAST Template Integration (Terraform) | Accepted | 2026-03-26 |
| [009](009-multi-database-abstraction.md) | Multi-Database Abstraction Layer | Accepted | 2026-03-26 |
| [010](010-agentcore-gateway-tool-routing.md) | AgentCore Gateway Tool Routing | Accepted | 2026-03-26 |
| [011](011-agentcore-observability.md) | AgentCore Observability (OpenTelemetry) | Accepted | 2026-03-26 |
| [012](012-multi-agent-orchestration.md) | Multi-Agent Orchestration (Step Functions) | Accepted | 2026-03-27 |
| [013](013-snowflake-iceberg-migration.md) | Snowflake → AWS Migration via Apache Iceberg | Accepted | 2026-03-27 |
| [014](014-dbt-mcp-integration.md) | dbt MCP Server Integration | Accepted | 2026-03-27 |
| [015](015-dsa-agent-integration.md) | DSA × PlatformAgent Integration (4-step UX, NL→SQL, source discovery) | Accepted | 2026-04-17 |

## Template

New ADRs should follow this format:

```markdown
# ADR-NNN: Title

**Status**: Proposed | Accepted | Deprecated | Superseded by ADR-NNN

**Date**: YYYY-MM-DD

## Context
What is the issue or requirement that motivates this decision?

## Options Considered
1. **Option A** — Description, pros, cons.
2. **Option B** — Description, pros, cons.

## Decision
What is the chosen option and why?

## Consequences
What are the positive and negative results of this decision?
```
