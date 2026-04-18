# ADR-014: dbt MCP Server Integration

**Status**: Accepted

**Date**: 2026-03-27

## Context

All five agents need to interact with dbt — the Migration Agent generates dbt projects, the Quality Agent runs dbt tests, the Enrichment Agent reads model metadata for descriptions, the Mapping Agent traverses dbt lineage for the knowledge graph, and the Query Agent uses the semantic layer for NL-to-SQL. We need a consistent, secure way to expose dbt capabilities to all agents.

## Options Considered

1. **Direct dbt CLI calls** — Each agent shells out to `dbt compile`, `dbt run`, etc. Simple but no authentication, no rate limiting, no centralized config. Each container needs dbt installed.
2. **dbt MCP Server (dbt-labs/dbt-mcp)** — MCP server providing 40+ tools. Runs as a sidecar or Gateway endpoint. Centralized auth and config. All agents share the same dbt project context.
3. **Custom dbt tools** — Write our own `@tool` wrappers for dbt operations. Maximum control but duplicates what dbt-mcp already provides.

## Decision

**dbt MCP Server** (dbt-labs/dbt-mcp v1.9.3) deployed as a sidecar alongside each agent container. Registered in AgentCore Gateway for centralized auth and rate limiting. Each agent accesses a curated subset of the 40+ tools based on its role (defined in `gateway/mcp/dbt-mcp-config.json`).

**Tool allocation:**
- Migration Agent: `generate_source`, `generate_staging_model`, `generate_model_yaml`, `compile`
- Enrichment Agent: `get_all_models`, `get_model_details`, `get_lineage`, `search`
- Quality Agent: `test`, `build`, `get_model_health`, `get_model_performance`
- Mapping Agent: `get_lineage`, `get_model_parents`, `get_model_children`, `get_all_sources`
- Query Agent: `execute_sql`, `text_to_sql`, `query_metrics`, `list_metrics`, `get_dimensions`

Cedar policies enforce tool-level access control: read-only tools for most agents, write tools (`generate_*`, `run`) only for the Migration Agent.

## Consequences

**Positive:**
- 40+ production-grade dbt tools maintained by dbt Labs — no custom code to maintain
- Centralized auth via AgentCore Gateway Cedar policies
- Consistent dbt project context across all agents
- MCP protocol means any Strands agent can discover and call tools automatically

**Negative:**
- Sidecar deployment adds container complexity
- dbt MCP server requires dbt Cloud credentials for full functionality (semantic layer API)
- Version coupling — we pin to v1.9.3, must track upstream releases
- Sidecar latency for stdio transport (mitigated by co-located containers)
