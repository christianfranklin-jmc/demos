# ADR-010: AgentCore Gateway Tool Routing

**Status**: Accepted

**Date**: 2026-03-26

## Context

The Platform Agent has 7 tools. When deployed to AgentCore Runtime, we must decide which tools run directly in the agent container vs. which are routed through the AgentCore Gateway as Lambda-backed MCP tools.

## Options Considered

1. **All tools direct** — Simplest deployment, all tools in the container. No Gateway overhead. But: database connections from the container require VPC peering, and tools can't scale independently.
2. **All tools in Gateway** — Maximum separation, but `generate_dbt_project` and `generate_semantic_layer` write files to the filesystem, which doesn't work in a stateless Lambda.
3. **Hybrid** — Data tools (connect, scan, profile, query, DDL) go through Gateway. Code-gen tools (dbt_generate, semantic_layer) stay direct in the agent container.

## Decision

**Hybrid approach**: 5 data tools route through AgentCore Gateway as a single Lambda target. 2 code-gen tools remain as direct Strands `@tool` functions in the agent container.

**Gateway tools**: `connect_to_database`, `scan_metadata`, `profile_database`, `run_query`, `execute_ddl` — these are stateless (each invocation creates a fresh database connection), don't need filesystem access, and benefit from independent scaling.

**Direct tools**: `generate_dbt_project`, `generate_semantic_layer` — these write files to `dbt_output/`, need YAML serialization libraries, and produce multi-file outputs that don't map well to Lambda's request/response model.

## Consequences

**Positive:**
- Data tools scale independently via Lambda concurrency
- Gateway handles OAuth2 M2M auth — agent doesn't manage DB credentials directly
- Lambda cold starts only affect the first query per warm instance
- Direct tools retain full filesystem access for code generation

**Negative:**
- OAuth2 token refresh adds ~100ms on first request per session
- Gateway adds a network hop for each data tool call
- Lambda packaging includes database drivers (psycopg2 + redshift_connector)
- Two deployment artifacts: Docker image (agent) + Lambda ZIP (gateway tools)
