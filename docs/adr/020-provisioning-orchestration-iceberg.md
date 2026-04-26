# ADR-020: Provisioning Orchestration into Iceberg

**Status**: In progress — initial Iceberg-driver decision (D1) landed in feature `002-dsa-hub-pinnacle` Phase 2; D2 (orchestration), D3 (validation threshold), and D4 (palette) land with US3 (Phase 5) per the in-flight Addendum E discipline.

**Date**: 2026-04-26 (D1); D2–D4 to be amended in-flight when their implementing commits land

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

### D2 — 7-agent DAG orchestrator with SSE schema v2 (Phase 5, T077–T079; **TBD — to amend**)

*Decision pending; will be amended into this ADR in the same commit as `src/platform_agent/provisioning/orchestrator.py`.*

Outline of the planned decision:

- DAG: `schema → pipeline → model → quality → mapping → {semantic, delivery}` (semantic and delivery run in parallel after mapping).
- Per-agent retry: only the failed agent and its downstream dependents re-execute; completed upstream artifacts are reused (cached by `run_id`).
- Event stream: schema **v2** of the existing SSE format, additive over v1. Envelope `{run_id, seq, ts, v: 2}` plus 11 new event kinds (`agent.started/progress/completed/failed`, `kpi.tick`, `artifact.produced`, `validation.started/result`, `run.completed`, `run.needs_replan`, `heartbeat`).
- State: per-run state lives in-memory keyed by `run_id`; durable per-Connection store records (entities, products, activity log) are written through as the run progresses so the audit chain survives even if the SSE consumer disconnects.
- Five existing agents (`schema`, `pipeline`, `model`, `quality`, `mapping`) are **promoted** from `patterns/migration-agent/` and `patterns/quality-agent/` into `src/platform_agent/provisioning/agents/`. Two new agents (`semantic`, `delivery`) are net-new.

Step Functions orchestration (the existing migration-suite plan) is deferred to deployed-mode and does not block v1 in-product flow.

### D3 — Validation threshold gate at 80 % default (Phase 5, T081 + T119–T120; **TBD — to amend**)

*Decision pending; will be amended into this ADR in the same commit as the threshold logic in `delivery_agent`.*

Outline of the planned decision:

- After mapping registers the Iceberg table, the `delivery-agent` runs each PRD `business_question` through the cross-source TTYD planner against the new table. An LLM-as-judge (Opus 4.7) evaluates each answer against the PRD's expected ranges.
- Threshold = `DSA_HUB_VALIDATION_THRESHOLD` (default `0.80`, matching SC-004).
- ≥ threshold → product state `final`; `ttyd_exposed = True` flipped atomically; product joins the TTYD `cross_source_query` source list.
- < threshold → product state `provisional`; visible in the catalog and on the Semantic page but not TTYD-exposed; the run emits `run.needs_replan`. A "Re-run from failed step" affordance re-executes only the validation step (or, optionally, the upstream agent that produced the schema gap).
- Successful rerun that lifts pass rate ≥ threshold flips `ttyd_exposed = True` atomically. Promotion is one-way in v1 (`provisional → final` only; never the reverse).

### D4 — Palette extension limited to two semantic-only roles (Phase 5, T089; **TBD — to amend**)

*Decision pending; will be amended into this ADR in the same commit that adds the CSS custom properties.*

Outline of the planned decision:

- Add two CSS custom properties: `--status-success: #16A34A` and `--status-error: #DC2626`.
- Used **only** for: agent DAG node states (active = phData Teal pulse, complete = success-green, failed = status-error), Validation Card ✓/✗ chips, connection card pulse dots.
- All other UI continues to use the strict phData palette (Navy / Blue / Teal / Orange + dark surfaces).
- This is the Article V deviation acknowledged in feature plan.md Complexity Tracking row 1.

**Alternatives considered for D4**:

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
