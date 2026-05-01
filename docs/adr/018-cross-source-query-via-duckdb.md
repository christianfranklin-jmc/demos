# ADR-018: Cross-Source TTYD via In-Process DuckDB Scratchpad

**Status**: Accepted (D1 — deterministic v1) in feature `002-dsa-hub-pinnacle` Phase 6 backend. D2 (Strands NL→SQL planner) reserved for in-flight amendment.

**Date**: 2026-04-26 (D1); D2 amended when the LLM planner lands.

**Feature**: `specs/002-dsa-hub-pinnacle/`

## Context

US4 needs cross-source Talk-to-Data: when the lens is "all sources" and the workspace has ≥2 live connections, the planner must (per FR-015..FR-020):

- Plan whether the question can be answered from one source or requires combining.
- Pull bounded subsets per source via `run_query` (250-row cap per FR-018).
- Materialize the pulls in an in-process scratchpad and run a join SQL (5,000-row cap on the joined result).
- Surface per-source chips + join chip + semantic-layer hits in the response.
- Block any non-SELECT/non-WITH SQL at every query path (SC-006).

The architecture splits cleanly into two layers:

1. **Scratchpad** — execute the join given pre-fetched per-source rows + a join SQL.
2. **Planner** — turn a free-text question into the plan (which sources, what to SELECT, what join SQL to run).

Layer 1 is mechanical and deterministic. Layer 2 is an LLM problem.

## Decisions

### D1 — In-process DuckDB as the scratchpad (Phase 6, T093)

**Decision**: Implemented `src/platform_agent/tools/duckdb_scratchpad.py` exposing
`cross_source_query(payload: CrossSourceQueryRequest) -> CrossSourceQueryResult`.

- Each call opens a fresh `:memory:` DuckDB connection; no data persists across turns.
- Per-source pulls arrive as `SourcePullResult(view_name, columns, rows, truncated_at_cap)` — already capped at 250 rows by the caller (re-validated at the scratchpad boundary).
- Each pull is registered as a typed `TEMP TABLE` (column types inferred from the first non-null sample value: BIGINT / DOUBLE / BOOLEAN / VARCHAR; all-null columns default to VARCHAR).
- The caller-supplied `join_sql` runs against the registered views. We wrap it in `SELECT * FROM ({join_sql}) AS _cross_source_join LIMIT {join_cap + 1}` so a missing/oversized LIMIT in the user's SQL still respects FR-018.
- Read-only enforcement: `assert_read_only(join_sql)` runs before any DuckDB execution; identifier names go through a strict `^[A-Za-z_][A-Za-z0-9_]*$` regex.
- Truncation flag set when fetched rows exceed `join_cap`.

**Rationale**: DuckDB is the established choice for in-process analytical joins in Python: zero deploy footprint, columnar engine, supports SQL parity that downstream planners speak. Caps protect demos from runaway joins. Per-turn lifetime means no stale state.

**Alternatives considered**:
- *Federated query in Snowflake* (external tables over Postgres): rejected — requires Snowflake-side configuration the customer demo doesn't control, and creates a Snowflake bias.
- *Materialize joins to Iceberg then query*: rejected — turns every TTYD question into a provisioning run; latency unacceptable (SC-005 ≤5s).
- *pandas merge*: rejected — not SQL; the LLM planner would need a translation layer above pandas.
- *Trino/Presto*: rejected — heavyweight infrastructure for a per-tab demo.
- *Type inference via pyarrow*: rejected for v1 — adds a heavyweight dep for marginal benefit; manual sample-based inference is sufficient for the seed-volume row counts.

### D2 — Strands NL→SQL planner — TBD

The planner that turns a free-text question into per-source pulls + join SQL is reserved for ADR-018 D2. Same swap pattern as the pill generator (ADR-021 D2): the contract surface stays stable; only the internals of the route's request body assembly change. v1 callers supply the plan directly via `POST /workflow/query/cross-source`.

## Implementation surface (D1)

- `src/platform_agent/tools/duckdb_scratchpad.py` — the scratchpad tool (140 LOC).
- `src/platform_agent/api/routes_query_cross_source.py` — `POST /workflow/query/cross-source`. Re-validates read-only on every SQL string; runs each pull through the right `DatabaseDriver`; emits `ttyd_query` activity-log entries; tracks per-workspace KPI counters.
- `tests/integration/test_duckdb_scratchpad.py` — 7 tests: real INNER JOIN against two pulls; cross-join hits the 5,000-row cap; per-source 250-row cap; read-only blocks; view-name pattern; duplicate-view rejection; empty-pulls rejection.
- `tests/contract/test_query_cross_source.py` — 5 tests: 400 cross_source_unavailable when <2 live connections; 400 read_only_violation in pull SQL; 400 read_only_violation in join SQL; happy-path returns chips + join_result + KPI snapshot; KPI increments across calls.

## Consequences

- **Demo flow now answerable**: a DSA can hit `/workflow/query/cross-source` with a question + per-source pull plan + join SQL and get a structured response.
- **No LLM dependency for v1 cross-source TTYD**: the scratchpad runs offline. The Pinnacle showcase narrative (SC-001) is testable without Bedrock.
- **D2 swap is a single function**: the planner that builds the request body is the only piece that changes when the LLM lands.

## Forward-references

- ADR-021 (pill generation) follows the same D1/D2 split — deterministic v1 with stable contract; LLM swap reserved.
- ADR-019 (redundancy gate) consumes the same `assert_read_only` helper.
- ADR-020 D2 (provisioning orchestrator) emits `validation.result` events that — in a follow-up — will use this same scratchpad to run the auto-validation queries.
