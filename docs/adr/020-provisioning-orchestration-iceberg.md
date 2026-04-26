# ADR-020: Provisioning Orchestration into Iceberg

**Status**: Accepted. D1 + D2 + D3 + D4 all landed in feature `002-dsa-hub-pinnacle` Phases 2 + 5.

**Date**: 2026-04-26 (D1 Phase 2; D2/D3 Phase 5 backend; D4 Phase 5 frontend)

**Feature**: `specs/002-dsa-hub-pinnacle/`

## Context

The 002 feature ends every accepted PRD by materializing a cross-source data product as an **Apache Iceberg table** registered in AWS Glue Catalog. To do this the platform needs:

1. A first-class Iceberg/Glue **driver** that fits the existing `DatabaseDriver` protocol so that:
   - Tools, the Connections page, and TTYD treat the Iceberg connection as a peer source (no special-casing).
   - The mapping-agent can register new tables in the same Connection's catalog that TTYD will then query.
2. An **orchestrator** that runs a 7-agent DAG (schema → pipeline → model → quality → mapping → {semantic, delivery}) with per-agent retry, streaming progress to the Build page via SSE.
3. A **validation threshold gate** (Q5) that promotes the resulting product from `provisional` to `final` only when the auto-validation pass rate is ≥ 80 %.
4. A small **palette extension** for status semantics on the agent DAG and Validation Card (Constitution Article V deviation, justified in feature plan.md Complexity Tracking row 1).

This ADR records all four decisions; D1 lands first, D2–D4 amended as their code lands.

## Decisions

### D1 — IcebergDriver follows the existing DatabaseDriver protocol (Phase 2, T016)

**Decision**: Implement `src/platform_agent/drivers/iceberg.py` with a class implementing `DatabaseDriver`. Connection scope is `(glue_database, s3_warehouse_uri, region)`. Reads use **pyiceberg** (`Catalog.load_table()` + `Table.scan()` with column pushdown and a 250-row scan-layer cap matching FR-018). Writes are constrained to `CREATE TABLE` registrations performed by the mapping-agent through pyiceberg directly — destructive DDL (DROP/TRUNCATE/ALTER) is blocked unconditionally per Constitution Addendum C. dbt support uses **dbt-glue**.

**Rationale**: Treating Iceberg as a peer driver under the existing protocol means tools, Connections page UI, redundancy reads, semantic-graph writes, and TTYD reads all work without special-casing. pyiceberg is the actively-maintained Python-native client and avoids a JVM dependency. dbt-glue is the natural materialization adapter when the target is Glue Catalog. The 250-row cap at the scan layer (not just post-fetch) is FR-018-compliant and preserves the read-only invariant.

**Alternatives considered**:
- *Athena over Iceberg*: rejected — adds an Athena query path and AWS coupling for read; pyiceberg reads directly from S3 metadata.
- *Spark / Glue interactive sessions*: rejected — heavyweight; killed local-mode parity.
- *Treat Iceberg only as a write target, not a connection*: rejected by clarification Q3 — the user explicitly adds it as a first-class third connection in the workspace.

### D2 — 7-agent DAG orchestrator with SSE schema v2 (Phase 5, T077–T079, T067, T068)

**Decision**: Implemented `src/platform_agent/provisioning/orchestrator.py` driving the 7-agent DAG `schema → pipeline → model → quality → mapping → {semantic, delivery}`. Per-agent retry via `reset_for_retry(run_id, agent_id)` resets the named agent + every downstream dependent to PENDING; completed upstream artifacts are reused (cached on the `AgentExecution` records of the in-memory `ProvisioningRun`).

Event stream is **schema v2** (`src/platform_agent/provisioning/events.py`), additive over the v1 SSE schema in `api/events.py`. Envelope `{run_id, seq, ts, v: 2}` carries 11 event kinds: `agent.started`, `agent.progress`, `agent.completed`, `agent.failed`, `kpi.tick`, `artifact.produced`, `validation.started`, `validation.result`, `run.completed`, `run.needs_replan`, `heartbeat`. Sequence numbers strictly increase within a run (verified by `tests/contract/test_provision_sse_v2.py`).

State: per-run state lives in-memory keyed by `run_id`; durable per-Connection store records (entities, products, activity log) are written through the `ConnectionStore` as the run progresses so the audit chain survives even if the SSE consumer disconnects (verified by `delivery_agent` writing the `IcebergDataProduct` via `make_store(target_connection_id).upsert_product(...)`).

**Agent v1 status (Phase 5 + Phase 10 promotions)**:

- `schema_agent` — **promoted in Phase 10**. Reads live driver metadata via `WorkspaceRegistry` + `_scan_connection`; emits `source_schema` per connection (with `tables_scanned` + `schemas_scanned`) plus a real `iceberg_ddl_plan` whose target column list comes from the PRD's `entities_proposed` (or, when empty, from `joins_identified` shared keys). Type map promoted verbatim from `patterns/migration-agent/tools/convert_to_iceberg.py` and extended for Postgres / Redshift idioms. Falls back to a stub when the workspace context isn't reachable so unit tests stay offline.
- `mapping_agent` — **promoted in Phase 10**. Reads schema_agent's `iceberg_ddl_plan`; attempts a real `pyiceberg.Catalog.create_table()` against the target IcebergDriver's Glue catalog. `register_status` ∈ {`created`, `already_exists`, `planned_only` (offline fallback), `error`}; the DAG continues regardless of the outcome — delivery_agent decides final/provisional based on validation, not on register success. The graceful fallback keeps tests offline-runnable.
- `pipeline_agent` — **promoted in Phase 10c**. Executes each SourcePullSpec through the live driver via `WorkspaceRegistry` (PostgreSQL/Redshift/Snowflake/Iceberg). On success, stages all per-source rows into a single Parquet file at `~/.dsa-hub/runs/<run_id>/<table>.parquet` via DuckDB's `COPY ... TO ... (FORMAT PARQUET, COMPRESSION ZSTD)` — the model_agent + downstream consumers can read this artifact directly. UNION-ALL across per-source views with a `_source_view` discriminator. Falls back to the deterministic stub when any pull's connection isn't live-reachable (uniform fallback — never half-real).
- `model_agent` — **promoted in Phase 10d**. Calls the existing `generate_dbt_project` tool to write a complete dbt project to disk at `~/.dsa-hub/runs/<run_id>/dbt/<table>/`. Reads schema_agent's column list for the mart SQL; one staging model per source pull. Real `dbt_model` artifacts point at the generated `.sql` files; `dbt_profile` artifact points at the project's `profiles.yml`. Falls back to the stub when generate_dbt_project is unavailable. **Smoke-tested end-to-end**: full DAG completes with all 7 agents in `completed` state and a real dbt project on disk.
- `quality_agent` — still a stub that emits realistic-looking artifacts (DQDL rule sets, dbt-test counts). Real body — invoke `dbt test` against the generated project + DQDL rule generation from `patterns/quality-agent/tools/quality_rules.py` — lands when the v1 demo needs it.
- `semantic_agent`, `delivery_agent` — real from the start (Phase 5). `semantic_agent` writes entities/metrics into the target ConnectionStore via the Protocol; `delivery_agent` runs auto-validation and flips the product final/provisional through `SQLiteConnectionStore.upsert_product` per the threshold gate.

The orchestrator + event-stream architecture is the load-bearing piece; agent internals continue to be promoted incrementally.

Step Functions orchestration (the existing migration-suite plan) is deferred to deployed-mode and does not block v1 in-product flow.

**Alternatives considered**:
- *Single monolithic agent*: rejected — kills the DAG visualization (Story 3) which is the headline UX for provisioning.
- *Polling-based progress*: rejected — SSE is already the established pattern in the repo and provides 1s update latency (US-3 acceptance #2).
- *Step Functions for v1 in-product flow*: rejected — adds AWS coupling for local-mode and is harder to test from pytest. Step Functions remains the deployed-mode option for the migration-suite branch.

### D3 — Validation threshold gate at 80 % default (Phase 5, T081)

**Decision**: Implemented in `src/platform_agent/provisioning/agents/delivery_agent.py`. After mapping registers the Iceberg table (as a provisional product), `delivery_agent.run` walks `prd.business_questions` and produces one `ValidationResult` per question.

- Threshold = `DSA_HUB_VALIDATION_THRESHOLD` env var (default `0.80`, matching SC-004).
- ≥ threshold → product state `final`; `ttyd_exposed = True`. Flip is atomic: same `store.upsert_product(product)` call writes `state=final` AND `ttyd_exposed=True`. Activity-log emits `PRODUCT_PROMOTED`.
- < threshold → product state `provisional`; `ttyd_exposed = False`. Run emits `run.needs_replan` with `suggested_agent=delivery`. Activity-log emits `PRODUCT_REGISTERED`.
- Promotion is one-way in v1 (`provisional → final` only; never the reverse). The `SQLiteConnectionStore.upsert_product` invariant enforces this at the storage layer.

**v1 validation policy**: deterministic stub — `_simulate_validation()` passes every odd-indexed question. Real LLM-as-judge (Opus 4.7) per R8 is a single-function replacement. Tests monkey-patch `_simulate_validation` to exercise both all-pass and all-fail paths.

**Alternatives considered**:
- *Roll back the Iceberg registration on partial fail*: rejected per Q5 — destroys provisioning work for a recoverable shortfall.
- *Auto-rerun without user input*: rejected — silently spending a build cycle violates Article VIII (loading/error states must be visible).
- *Hardcode 80%*: rejected — env-driven for future flexibility, but defaults to the spec'd line.

### D4 — Palette extension limited to two semantic-only roles (Phase 5, T089)

**Decision**: Added two CSS custom properties to `frontend/src/styles/tokens.css`:

```css
--status-success: #16A34A;
--status-error:   #DC2626;
```

Usage is scoped — by code comment + by where they're consumed — to:
- Agent DAG node ring color (`AgentDAG.tsx`): active = phData Teal pulse, complete = success-green, failed = status-error.
- Validation Card ✓/✗ glyphs (`Build.tsx`).
- Connection card pulse dot (`ConnectionCard.tsx` already inlined the same hexes; replacing with var() is mechanical).
- ActivityStream level dots (info=tertiary, success=success-green, warn=phData Orange, error=status-error).

All other UI continues to use the strict phData palette (Navy / Blue / Teal / Orange + dark surfaces). This is the Article V deviation justified in feature plan.md Complexity Tracking row 1.

**Alternatives considered**:
- *Use the user input's full accent palette* (`#00d4a0`, `#fbbf24`, `#4f8fff`, `#a855f7`, `#f472b6`): rejected — five off-brand colors is a much larger Article V deviation; only success/error are load-bearing for status semantics.
- *Use icons + greyscale only*: rejected — color-blind-unsafe for binary status; "green check / red x" is the universal idiom.
- *Use phData Orange for "failed"*: rejected — Orange is an accent color, not a danger signal; conflates with active states.

## Consequences

- **D1 (now)**: IcebergDriver lives in the driver registry alongside `postgresql`, `redshift`, `snowflake`, `databricks`. Adding it satisfies FR-002. The driver is symmetric for read+write within Constitution Addendum C constraints.
- **D2 (when landed)**: A complete provisioning run is observable as a stream of v2 SSE events. Per-agent retry is the unit of recovery, not whole-run rerun. Build-page UX is fully driven from the event stream.
- **D3 (when landed)**: Provisioning never destroys work — partial-success runs leave a queryable provisional artifact and a clear path to promotion. The 80% number is configurable but defaults to the spec'd line (SC-004).
- **D4 (when landed)**: phData palette stays strict everywhere except two status roles, where the deviation is necessary and color-blind-conscious.

## Forward-references

- ADR-018 (cross-source via DuckDB) — paired with this ADR via the validation flow, since the delivery-agent uses the cross-source planner.
- ADR-019 (redundancy gate) — runs before this ADR's orchestrator; outputs feed into the `POST /workflow/provision` precondition.
- ADR-021 (pill generation) — produces the PRDs that this ADR's orchestrator materializes.
