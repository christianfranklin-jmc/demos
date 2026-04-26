# Phase 1 Data Model: DSA Hub — Pinnacle Cross-Source

**Date**: 2026-04-26
**Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Research**: [research.md](./research.md)

This document specifies the entities, fields, relationships, validation rules, and state transitions used by the feature. Field types are language-agnostic (mapped to Pydantic v2 in the backend and TypeScript interfaces on the frontend). Persistence layout is described in research.md R2.

---

## Entity catalog (high-level)

```
Workspace ─owns─→ Connection (1..N, in-memory; per-tab)
Connection ─owns─→ ConnectionStore (durable, per-connection_id)
  ConnectionStore ⊃ {SemanticEntity, PhysicalBinding, Metric, Join,
                     IcebergDataProduct, ActivityLogEntry, DiscoveryCache}

Workspace ─runs─→ DiscoveryRun → BusinessProcess (per connection)
                                → CoverageMatrix (workspace-level)
                                → PillSuggestion (workspace-level)

PillSuggestion ─drafts→ PRD ─checked-by→ RedundancyReport ─→ ProvisioningRun
ProvisioningRun ─runs→ AgentExecution (1..7) ─produces→ Artifact
ProvisioningRun ─terminates-by→ IcebergDataProduct (final | provisional)
ProvisioningRun ─auto-validates→ ValidationResult (per business question)
```

Cross-connection links are intentionally limited (Q2): no entity in v1 spans multiple connections. The Iceberg connection's store accumulates entries from each ProvisioningRun that targets it.

---

## 1. Workspace

Per-tab in-memory record. Identified by the existing per-tab session UUID.

| Field | Type | Notes |
|---|---|---|
| `workspace_id` | `UUID` | Same value as the existing `sessionId` from `frontend/src/lib/session.ts`. Backend accepts either header for one minor version (FR-006). |
| `created_at` | `datetime` | First time the tab interacted with the backend. |
| `connections` | `list[Connection]` | Ordered by add time. ≤ ~10 by design. |
| `active_lens` | `Lens` | `"all"` or `{connection_id}`; default `"all"` once ≥2 connections live. |
| `activity_log_session` | `list[ActivityLogEntry]` | In-memory tail of per-tab actions; durable copies live in per-connection stores. |

**Validation**:
- `workspace_id` MUST be a v4 UUID.
- A workspace with 0 live connections cannot draft a PRD or run discovery; the UI surfaces an empty state rather than allowing the action.
- Workspace state is not serialized to disk in v1.

**Lifecycle**: `created → active (≥1 connection) → discarded (tab close)`.

---

## 2. Connection

A single source binding within a workspace. Drives a `DatabaseDriver` instance behind the scenes.

| Field | Type | Notes |
|---|---|---|
| `connection_id` | `str` | SHA-256 of `(driver_type, normalized_endpoint, scope)` per research R2. Stable across sessions. |
| `driver_type` | `enum` | `postgresql`, `redshift`, `snowflake`, `databricks`, `iceberg`. |
| `display_name` | `str` | User-supplied label (e.g., "Pinnacle Postgres"). 1–80 chars. |
| `endpoint` | `str` | Driver-specific endpoint string (host:port for SQL, account.region for SF, glue_db_arn for Iceberg). |
| `scope` | `str` | Database/schema scope (e.g., `northwinds.public`, `PINNACLE_FINANCIAL_DEMO_ASINGH.ANALYTICS`, `<glue_db>`). |
| `credential_ref` | `str \| None` | Local mode: in-memory key into the per-tab session secret cache. Deployed: Secrets Manager ARN. Never the credential itself. |
| `status` | `enum` | `connecting`, `scanning`, `live`, `error`. |
| `error` | `ConnectionError \| None` | When `status=error`: `{code, message, retryable: bool}`. |
| `kpis` | `ConnectionKPIs` | `{tables_total, rows_estimated, processes_detected, last_synced_at}`. |
| `added_at` | `datetime` | |
| `last_synced_at` | `datetime \| None` | Last successful `scan_metadata`. |
| `tags` | `list[str]` | UI labels (e.g., `["pinnacle", "operational"]`); free-form; not used by logic in v1. |

**Validation**:
- `(driver_type, endpoint, scope)` is unique within a workspace; adding a second connection with identical tuple is a no-op.
- `display_name` MUST be unique within a workspace (enforced UI-side; backend lets duplicates pass for resilience).
- For `driver_type=iceberg`, `endpoint` MUST be a valid Glue database ARN or `glue://<region>/<db>` URI; `scope` MUST be the Glue DB name.

**Lifecycle**:
```
connecting → scanning → live          (happy path)
connecting → error                    (creds wrong / network)
scanning → error                      (permissions / driver crash)
live → scanning → live                (re-sync, no error reset)
error → connecting → ...              (user retry from card)
```

**FR refs**: FR-001..FR-006, US-1.

---

## 3. ConnectionStore (durable per-connection storage)

Logical entity backed by SQLite (local) or DynamoDB (deployed) — see research R2. Holds the per-connection SemanticGraph + product registry + activity log.

| Sub-entity | Cardinality | Persistence kind |
|---|---|---|
| SemanticEntity | many | rows in `entities` table / partition |
| PhysicalBinding | many | rows in `physical_bindings` |
| Metric | many | rows in `metrics` |
| Join | many | rows in `joins` |
| IcebergDataProduct | many (only for iceberg-driver connections) | rows in `products` |
| ActivityLogEntry | many | rows in `activity_log`, append-only |
| DiscoveryCache | 1 | latest discovery snapshot, single-row |

**Validation**:
- Every sub-entity carries `connection_id` matching the store; cross-store joins are not permitted in v1 (Q2).
- Append-only invariant on `activity_log`; no in-place edits.

---

## 4. SemanticEntity

Business concept scoped to a single connection (Q2).

| Field | Type | Notes |
|---|---|---|
| `entity_id` | `str` | UUID. |
| `connection_id` | `str` | Owner connection. |
| `name` | `str` | Canonical business name (e.g., `client`, `advisor`, `engagement_score`). |
| `domain` | `enum` | One of the standards-approved Pinnacle domains: `wealth_mgmt`, `accounting`, `crm`, `hr`, `planning`, plus `unspecified`. |
| `attributes` | `list[Attribute]` | See below. |
| `metric_ids` | `list[str]` | FK to `Metric`. |
| `physical_binding_ids` | `list[str]` | FK to `PhysicalBinding`. ≥1 required. |
| `created_by_run_id` | `str \| None` | The `ProvisioningRun.run_id` that introduced this entity, if any. |
| `created_at` / `updated_at` | `datetime` | |
| `version` | `int` | Bumps on every metric/attribute change. |

### Attribute (embedded)

| Field | Type | Notes |
|---|---|---|
| `name` | `str` | Lower-snake. |
| `data_type` | `str` | Source-typed (e.g., `numeric(18,2)`, `varchar(255)`). |
| `is_pii` | `bool` | Informational only in v1 (Q4). |
| `description` | `str \| None` | LLM- or user-authored. |

**Validation**:
- `name` unique within `(connection_id, name)`.
- ≥1 `physical_binding_ids` required (no orphan entities).
- v1: NO field linking to entities in other connections (FR-022 / Q2).

**FR refs**: FR-021..FR-025, US-5.

---

## 5. PhysicalBinding

Maps a SemanticEntity to a specific table within a single connection.

| Field | Type | Notes |
|---|---|---|
| `binding_id` | `str` | UUID. |
| `entity_id` | `str` | FK to SemanticEntity. |
| `connection_id` | `str` | Same as the entity's connection. |
| `fully_qualified_name` | `str` | `<scope>.<schema>.<table>` (e.g., `northwinds.public.clients`). |
| `column_map` | `dict[str, str]` | Entity attribute name → physical column name. |
| `row_count_estimate` | `int \| None` | From last scan. |
| `last_validated_at` | `datetime \| None` | Last time the column_map was reconciled with live schema. |

**Validation**:
- `fully_qualified_name` MUST resolve to a live table (driver `scan_metadata` confirms).
- All keys of `column_map` MUST be attribute names of the parent entity.

---

## 6. Metric

Approved metric definition, scoped to a connection's graph.

| Field | Type | Notes |
|---|---|---|
| `metric_id` | `str` | UUID. |
| `connection_id` | `str` | Owner. |
| `name` | `str` | Canonical name (e.g., `gross_fee_revenue_q1`). |
| `definition_sql` | `str` | MetricFlow-compatible SQL. |
| `entity_ids` | `list[str]` | Entities the metric joins/aggregates. |
| `unit` | `str \| None` | e.g., `usd`, `count`, `percent`. |
| `created_by_run_id` | `str \| None` | |
| `version` | `int` | |

**Validation**:
- `definition_sql` MUST be SELECT/WITH-only (read-only enforcement).
- `entity_ids` MUST all share the same `connection_id`.

**FR refs**: FR-019, FR-021, FR-038.

---

## 7. Join

Recorded join between two entities **within the same connection** (Q2).

| Field | Type | Notes |
|---|---|---|
| `join_id` | `str` | UUID. |
| `connection_id` | `str` | |
| `left_entity_id` | `str` | |
| `right_entity_id` | `str` | Same connection as `left_entity_id`. |
| `join_keys` | `list[tuple[str, str]]` | (left_attr, right_attr) pairs. |
| `cardinality` | `enum` | `one_to_one`, `one_to_many`, `many_to_many`. |

---

## 8. BusinessProcess (discovered)

Output of per-connection discovery; not persisted long-term, but cached in `DiscoveryCache`.

| Field | Type | Notes |
|---|---|---|
| `process_id` | `str` | UUID. |
| `connection_id` | `str` | |
| `name` | `str` | E.g., `Accounts Payable`, `Client Fee Billing & Revenue`. |
| `domain` | `enum` | Same enum as SemanticEntity.domain. |
| `volume_signal` | `VolumeSignal` | `{row_count: int, dollar_total: Decimal \| None, currency: str \| None}`. |
| `last_activity_ts` | `datetime \| None` | From the data itself (most recent `created_at`/`posted_at`). |
| `sparkline` | `list[float]` | 12 buckets representing activity over the dataset's time range. |
| `backing_tables` | `list[str]` | Fully-qualified names contributing to the process. |

**Validation**:
- For Pinnacle Postgres, the discoverer MUST emit exactly 8 processes by name (FR-008): AP, Billing, CRM, Portfolio Mgmt & Trading, Performance & Asset Reporting, FP&A, GL, HR & Cost Mgmt. Test asserts the set.

**FR refs**: FR-007..FR-010.

---

## 9. CoverageMatrix (workspace-level)

Computed at the workspace level by merging per-connection BusinessProcess lists.

| Field | Type | Notes |
|---|---|---|
| `matrix_id` | `str` | UUID per discovery run. |
| `workspace_id` | `UUID` | |
| `rows` | `list[CoverageRow]` | One row per detected process. |

### CoverageRow (embedded)

| Field | Type | Notes |
|---|---|---|
| `process_name` | `str` | |
| `per_connection` | `dict[connection_id, ProcessPresence]` | |
| `shared_keys` | `list[str]` | Business keys present in ≥2 connections (e.g., `client_id`). |
| `ready_to_combine` | `bool` | `True` iff process appears in ≥2 connections AND `shared_keys` is non-empty. |

**Validation**:
- `ready_to_combine` is purely a coverage signal — it does NOT imply v1 entity reconciliation (Q2). It tells the pill agent that a cross-source pill is *possible*.

**FR refs**: FR-010.

---

## 10. PillSuggestion

Generated by the pill-agent (research R5).

| Field | Type | Notes |
|---|---|---|
| `pill_id` | `str` | UUID per workspace per generation. |
| `title` | `str` | E.g., "Client 360", "Revenue Waterfall". |
| `subtitle` | `str` | E.g., "combines: Postgres + Snowflake". |
| `icon` | `str` | Lucide icon name. |
| `target_iceberg_table` | `str` | Required FQN like `iceberg.pinnacle_360.fct_client_360`. |
| `source_connection_ids` | `list[str]` | ≥1; ≥2 for cross-source pills (the typical case). |
| `estimated_build_minutes` | `int` | LLM-estimated, used for the build-page ETA seed. |
| `seed_prd_body` | `PRDDraft` | Pre-populated PRD content (entities, joins, business questions). |
| `generated_at` | `datetime` | |

**Validation**:
- `target_iceberg_table` MUST start with `iceberg.` and have exactly three dot segments.
- `source_connection_ids` MUST all be live in the workspace at generation time.
- Workspace MUST have ≥6 PillSuggestions for Pinnacle (SC-003); the pill-agent retries up to 2x if it under-produces.

**FR refs**: FR-011..FR-013, FR-014.

---

## 11. PRD (Product Requirements Doc — drafted)

Draft state of the data product. Not persisted in v1 beyond the workspace memory + activity log; final form lives inside the `IcebergDataProduct.prd_snapshot` field on registration.

| Field | Type | Notes |
|---|---|---|
| `prd_id` | `str` | UUID per draft. |
| `workspace_id` | `UUID` | |
| `title` | `str` | |
| `target` | `IcebergTarget` | `{connection_id, glue_db, table_name}`. |
| `entities_proposed` | `list[ProposedEntity]` | New entities the product introduces (name, attributes, source). |
| `metrics_proposed` | `list[ProposedMetric]` | |
| `joins_identified` | `list[ProposedJoin]` | Cross-source joins to be materialized. |
| `business_questions` | `list[str]` | The questions the product must answer (drives auto-validation). ≥1 required. |
| `source_pulls` | `list[SourcePullSpec]` | Per-source SELECTs that the pipeline-agent will execute. |
| `standards_applied` | `list[str]` | Footer entries (FR-038). |
| `origin` | `enum` | `pill` \| `manual`. |
| `created_at` / `updated_at` | `datetime` | |

**Validation**:
- `target.connection_id` MUST resolve to a live `iceberg`-driver connection (FR-031, Q3); otherwise acceptance is blocked.
- `business_questions` non-empty (auto-validation depends on it).
- `standards_applied` MUST be non-empty (SC-011).

**FR refs**: FR-013, FR-026..FR-038, US-2/US-3/US-7.

---

## 12. RedundancyReport

Output of the redundancy-agent between draft and acceptance.

| Field | Type | Notes |
|---|---|---|
| `report_id` | `str` | UUID. |
| `prd_id` | `str` | FK. |
| `target_connection_id` | `str` | The connection whose graph was scanned (Q2). |
| `state` | `enum` | `net_new`, `partial_overlap`, `duplicate`. |
| `overlaps` | `list[OverlapItem]` | Per-overlap details. |
| `decision` | `Decision \| None` | Set when user resolves: `{kind: "reuse" \| "override", entity_or_metric_id, rationale: str}`. |
| `generated_at` | `datetime` | |

### OverlapItem

| Field | Type | Notes |
|---|---|---|
| `proposed_name` | `str` | From PRD. |
| `existing_id` | `str` | Existing SemanticEntity or Metric id in the target store. |
| `kind` | `enum` | `entity` or `metric`. |
| `overlap_pct` | `float` | 0–100 attribute overlap. |
| `side_by_side_diff` | `str` | Markdown diff for the UI. |

**Validation**:
- `state=duplicate` blocks acceptance until `decision.kind="override"` with non-empty rationale.
- `state=partial_overlap` blocks until every overlap has a decision recorded.
- `state=net_new` requires no decision and proceeds.

**FR refs**: FR-026, US-6.

---

## 13. ProvisioningRun

Tracks one execution of the 7-agent DAG.

| Field | Type | Notes |
|---|---|---|
| `run_id` | `str` | UUID. Used in the SSE URL. |
| `workspace_id` | `UUID` | |
| `prd_id` | `str` | FK. |
| `target_connection_id` | `str` | The Iceberg connection. |
| `state` | `enum` | `queued`, `running`, `completed`, `failed`, `needs_replan`. |
| `agents` | `list[AgentExecution]` | One per DAG node, in dependency order. |
| `kpi_series` | `list[KpiTick]` | Time-series of KPI tile values for replay. |
| `started_at` / `completed_at` | `datetime \| None` | |
| `validation_pass_rate` | `float \| None` | 0..1. Null until validation completes. |
| `final_product_id` | `str \| None` | FK to IcebergDataProduct. Set when registration occurs (regardless of final/provisional). |

### AgentExecution

| Field | Type | Notes |
|---|---|---|
| `agent_id` | `enum` | `schema`, `pipeline`, `model`, `quality`, `mapping`, `semantic`, `delivery`. |
| `state` | `enum` | `pending`, `active`, `completed`, `failed`, `retrying`. |
| `started_at` / `completed_at` | `datetime \| None` | |
| `attempt` | `int` | 1-indexed. |
| `artifacts` | `list[Artifact]` | Produced artifacts (column lists, dbt model paths, Iceberg table names). |
| `error` | `AgentError \| None` | When `state=failed`. |
| `latency_ms_p95` | `int \| None` | For the build-page KPI tile. |

**Validation**:
- DAG dependency order enforced: `schema → pipeline → model → quality → mapping → {semantic, delivery in parallel after mapping}`.
- A run that fails before mapping does NOT register a product (no `final_product_id`).
- A run that completes mapping but fails semantic/delivery DOES register a product (in provisional state at minimum) and surfaces the failed agent for retry.

**Lifecycle**:
```
queued → running                          (orchestrator picks up)
running → completed                       (validation pass rate ≥ threshold)
running → needs_replan                    (validation pass rate < threshold OR a non-mapping agent failed)
running → failed                          (mapping agent failed; no product registered)
needs_replan → running                    (user clicks "Re-run from failed step")
needs_replan → completed                  (rerun lifts pass rate ≥ threshold)
```

**FR refs**: FR-027..FR-032, FR-035, US-3.

---

## 14. IcebergDataProduct

The terminal artifact; lives in the target Iceberg connection's store.

| Field | Type | Notes |
|---|---|---|
| `product_id` | `str` | UUID. |
| `connection_id` | `str` | Target Iceberg connection. |
| `table_name` | `str` | E.g., `iceberg.pinnacle_360.fct_client_360`. |
| `state` | `enum` | `final`, `provisional`. (Q5) |
| `ttyd_exposed` | `bool` | True iff `state=final`; toggled atomically by delivery-agent. |
| `created_by_run_id` | `str` | FK to ProvisioningRun. |
| `prd_snapshot` | `PRD` | Full PRD body at acceptance (frozen). |
| `validation_pass_rate` | `float` | At time of registration; updated on rerun promotion. |
| `validation_results` | `list[ValidationResult]` | Latest run's results. |
| `entity_ids_introduced` | `list[str]` | Pointers into the same connection's SemanticEntity rows. |
| `metric_ids_introduced` | `list[str]` | |
| `created_at` / `updated_at` | `datetime` | |

**Validation**:
- `state` transitions: `provisional → final` only; never `final → provisional` in v1 (immutable promotion).
- `ttyd_exposed = (state == "final")` is an invariant.

**FR refs**: FR-031, FR-033..FR-036, US-3, US-6.

---

## 15. ValidationResult

Per-question result from the auto-validation pass.

| Field | Type | Notes |
|---|---|---|
| `result_id` | `str` | UUID. |
| `run_id` | `str` | FK. |
| `question` | `str` | Verbatim from PRD.business_questions. |
| `state` | `enum` | `pending`, `passed`, `failed`. |
| `sql_executed` | `str \| None` | The SQL the planner ran. |
| `result_preview` | `list[dict]` \| None | Up to 20 rows. |
| `latency_ms` | `int \| None` | |
| `judge_reasoning` | `str \| None` | LLM-as-judge explanation. |
| `evaluated_at` | `datetime \| None` | |

**Validation**:
- A `failed` row MUST include a `judge_reasoning` and SHOULD include `sql_executed` (unless the planner refused to generate SQL).

**FR refs**: FR-033..FR-036, US-6.

---

## 16. ActivityLogEntry

Append-only audit row. Lives in **each connection's** store (the connection that "owns" the action: e.g., a discovery hit lands in the source connection's log; a registration lands in the Iceberg connection's log; a redundancy decision lands in the target Iceberg connection's log).

| Field | Type | Notes |
|---|---|---|
| `entry_id` | `str` | UUID. |
| `connection_id` | `str` | Owner. |
| `workspace_id` | `UUID` | The tab that produced the action (kept for audit, not for joins). |
| `kind` | `enum` | `connection_added`, `connection_error`, `connection_retried`, `discovery_completed`, `pill_clicked`, `prd_drafted`, `redundancy_decision`, `provisioning_started`, `agent_state_change`, `validation_result`, `product_registered`, `product_promoted`, `ttyd_query`. |
| `payload` | `dict` | Kind-specific shape. |
| `ts` | `datetime` | |

**Validation**:
- Append-only; no edits or deletes.
- Reconstructing a run from logs MUST produce the same chain (SC-008).

**FR refs**: FR-032, SC-008.

---

## State machines (consolidated)

### Connection
`connecting → scanning → live` (happy)
`* → error → connecting` (retry path)

### ProvisioningRun
`queued → running → {completed | needs_replan | failed}`
`needs_replan → running → {completed | needs_replan}` (rerun loop)

### IcebergDataProduct
`provisional → final` (one-way)

### Validation per-question
`pending → {passed | failed}`

---

## Cross-cutting invariants

1. **No cross-connection reference** in v1 (Q2). Every persisted entity carries a single `connection_id`; foreign keys never cross stores.
2. **Read-only at every query path** (FR-018, SC-006). All `definition_sql`, `source_pulls.sql`, and ad-hoc TTYD planner output MUST pass the SELECT/WITH-only regex before execution.
3. **Iceberg connection presence** is a precondition for ProvisioningRun creation (FR-031, Q3). Backend rejects `POST /workflow/provision` if the workspace's connection list contains zero `driver_type=iceberg` connections in `live` state.
4. **Validation threshold** (Q5) is config-driven via `DSA_HUB_VALIDATION_THRESHOLD` env (default 0.80). Promotion to `final` is atomic — flip happens in the same store transaction that updates `validation_pass_rate` post-rerun.
5. **Append-only activity log** for audit reconstructibility (SC-008).
6. **Three-frontend rule** (Article II): every entity reachable from the React UI has a CLI text-mode equivalent surface (e.g., `dsa-hub workspace list-connections`, `dsa-hub provision status <run_id>`).
