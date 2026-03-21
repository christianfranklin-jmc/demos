# ADR-006: Data Connectivity Layer

**Status**: Accepted

**Date**: 2026-03-21

## Context

The agent needs to connect to AWS data services, scan metadata, profile columns, run queries, and execute DDL. The PRD specifies phData Toolkit as the data connectivity layer, but the agent also needs interactive SQL execution with structured result sets (columns + rows) that Toolkit's CLI doesn't return.

## Options Considered

1. **phData Toolkit CLI + psycopg2 hybrid** — Toolkit CLI (`toolkit ds scan`, `toolkit ds profile`) for metadata scanning and column-level profiling (richer output: ERD graph, constraints, statistics). psycopg2 for interactive queries and DDL execution where structured result sets are needed.
2. **Toolkit CLI only** — Use `toolkit ds exec` for all database operations. Limitation: `ds exec` returns scalar output, not structured JSON result sets with column names and typed rows.
3. **psycopg2 only** — Direct SQL against `information_schema` for metadata. Works but produces less rich metadata than Toolkit (no ERD graph, no column-level profiling stats without custom queries).
4. **SQLAlchemy** — ORM-based approach. Over-abstracted for this use case; the agent generates raw SQL and needs direct result set access.

## Decision

Use a **hybrid approach**: phData Toolkit CLI for scan/profile, psycopg2 for query/DDL. The adapter (`_toolkit_client.py`) auto-detects Toolkit availability and falls back to psycopg2 for scanning if Toolkit is not installed.

## Consequences

- **Positive**: Best of both worlds — Toolkit's rich metadata (ERD graph, constraint details, column statistics) plus psycopg2's structured query results.
- **Positive**: Graceful degradation — agent works without Toolkit installed (psycopg2 fallback for scan).
- **Positive**: Single adapter module to swap when Toolkit adds a Python SDK or REST API.
- **Negative**: Two dependencies for database access (Toolkit CLI subprocess + psycopg2 library).
- **Negative**: Toolkit CLI invocation adds subprocess overhead (~1-2s per call); acceptable for scan/profile which are infrequent.
