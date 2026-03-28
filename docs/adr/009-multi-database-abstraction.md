# ADR-009: Multi-Database Abstraction Layer

**Status**: Accepted

**Date**: 2026-03-26

## Context

The Platform Agent's data tools (`_toolkit_client.py`) are hardcoded to PostgreSQL via psycopg2. To support Redshift, Snowflake, and Databricks, we need an abstraction that lets tools work against any database without knowing the specifics.

Each database has different:
- Python connectors (psycopg2, redshift_connector, snowflake-connector-python, databricks-sql-connector)
- System catalog queries for metadata (pg_stat_user_tables vs SVV_TABLE_INFO vs ACCOUNT_USAGE)
- dbt adapters (dbt-postgres, dbt-redshift, dbt-snowflake, dbt-databricks)
- Authentication methods (password, IAM, key-pair, PAT)

## Options Considered

1. **Keep psycopg2 hardcoded** — Simplest, but limits the agent to PostgreSQL-compatible databases only.
2. **SQLAlchemy** — Full ORM with dialect system. Heavyweight, metadata queries would still need per-database SQL, and the ORM abstraction adds unnecessary complexity for our read-heavy use case.
3. **Custom DatabaseDriver protocol** — Minimal Python Protocol class. Each driver implements connect, query, scan_metadata, and dbt config methods. No ORM overhead, each driver owns its catalog queries.

## Decision

Introduce a **DatabaseDriver Protocol** in `src/platform_agent/drivers/base.py`. Each database gets its own file implementing the protocol. Drivers are registered in a `DRIVER_REGISTRY` and loaded lazily (optional imports) so installing `redshift_connector` is only required when using Redshift.

## Consequences

**Positive:**
- Adding a new database = one Python file + one optional dependency
- Tools program against the protocol — zero changes when adding databases
- `generate_dbt_project` reads `driver.get_dbt_adapter()` — profiles.yml always matches
- Gateway Lambda uses the same drivers — no code duplication
- Optional dependencies keep the base install lean

**Negative:**
- Each driver reimplements scan_metadata SQL (no shared base class) — acceptable because the SQL genuinely differs per database
- Must maintain compatibility across driver versions
- Profiling depth varies per driver (Toolkit CLI enhances PostgreSQL but not others)
