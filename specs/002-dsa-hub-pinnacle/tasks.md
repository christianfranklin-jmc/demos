---
description: "Task list — DSA Hub Pinnacle Cross-Source"
---

# Tasks: DSA Hub — Pinnacle Cross-Source

**Input**: Design documents from `specs/002-dsa-hub-pinnacle/`
**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/](./contracts/), [quickstart.md](./quickstart.md)
**Tests**: Included — the spec input + plan.md explicitly call for contract tests on every new endpoint, and SC-007 requires the existing 51 pytest + vitest cascade suite to keep passing.

## Format: `[ID] [P?] [Story] Description`

- **[P]** = parallelizable (different files, no incomplete dependencies)
- **[Story]** = which user story this task belongs to (US1–US7)
- All paths are absolute relative to the repo root `/Users/mwebb/Projects/dsa-platform/`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization for the new feature.

- [X] T001 Add new Python deps via `uv add duckdb pyiceberg dbt-glue` in `pyproject.toml`; lock with `uv lock`; verify `uv pip install -e ".[dev,redshift,snowflake,otel]"` still resolves cleanly
- [X] T002 [P] Add new env-var documentation to `.env.example`: `STORAGE_BACKEND`, `DSA_HUB_VALIDATION_THRESHOLD`, `DSA_HUB_DUCKDB_JOIN_CAP`, `DSA_HUB_SOURCE_PULL_CAP`, `ICEBERG_DEFAULT_GLUE_DB`, `DSA_HUB_DEMO_MODE` (per `quickstart.md` §3)
- [X] T003 [P] Configure ruff + mypy strict for new module roots in `pyproject.toml`: add `src/platform_agent/workspace/`, `src/platform_agent/provisioning/`, `src/platform_agent/semantic/` to mypy strict allow-list (Constitution Article III)
- [X] T004 [P] Create empty package skeletons with `__init__.py` files for: `src/platform_agent/workspace/`, `src/platform_agent/provisioning/`, `src/platform_agent/provisioning/agents/`, `src/platform_agent/semantic/`, `src/platform_agent/semantic/migrations/`
- [X] T005 [P] Frontend: ensure `react-flow` (or `@xyflow/react`) is on the lockfile in `frontend/package.json`; add it via `pnpm add` if not already there (used by both Build-page DAG and Semantic-page graph) — verified `@xyflow/react ^12.10.2` already present
- [X] T006 [P] Add `frontend/src/lib/agentcore-client/parsers/v2/` directory with a stub `index.ts` that re-exports the v1 parser API (additive extension; v2 parser is fleshed out under US3)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core data model + workspace + driver layer + per-connection storage. Every user story depends on these.

**⚠️ CRITICAL**: No US-phase task can begin until Phase 2 is complete (sole exception: docs-only US7 work in Phase 9 can lay-down content templates in parallel since it doesn't touch live code paths).

### Pydantic models — ALL entities from data-model.md

- [ ] T007 [P] Create `src/platform_agent/workspace/models.py` with Pydantic v2 models: `Workspace`, `Connection`, `ConnectionKPIs`, `ConnectionError`, `Lens` (data-model.md §1, §2)
- [ ] T008 [P] Create `src/platform_agent/semantic/models.py` with Pydantic v2 models: `SemanticEntity`, `Attribute`, `PhysicalBinding`, `Metric`, `Join` (data-model.md §4, §5, §6, §7)
- [ ] T009 [P] Create `src/platform_agent/workflow/discovery_models.py` with `BusinessProcess`, `VolumeSignal`, `CoverageMatrix`, `CoverageRow`, `ProcessPresence` (data-model.md §8, §9)
- [ ] T010 [P] Create `src/platform_agent/workflow/pill_models.py` with `PillSuggestion`, `PRDDraft`, `ProposedEntity`, `ProposedMetric`, `ProposedJoin`, `SourcePullSpec`, `IcebergTarget` (data-model.md §10, §11)
- [ ] T011 [P] Create `src/platform_agent/provisioning/models.py` with `ProvisioningRun`, `AgentExecution`, `AgentError`, `Artifact`, `KpiTick`, `RedundancyReport`, `OverlapItem`, `Decision`, `IcebergDataProduct`, `ValidationResult` (data-model.md §12, §13, §14, §15)
- [ ] T012 [P] Create `src/platform_agent/workspace/activity_models.py` with `ActivityLogEntry` and the kind enum (data-model.md §16). Enumerate all 13 kinds upfront so per-feature tasks don't need conditional enum edits: `connection_added`, `connection_error`, `connection_retried`, `discovery_completed`, `pill_clicked`, `prd_drafted`, `redundancy_decision`, `provisioning_started`, `agent_state_change`, `validation_result`, `product_registered`, `product_promoted`, `ttyd_query`.

### Per-tab session header alias (FR-006)

- [ ] T013 Update `src/platform_agent/api/deps.py` to accept `X-DSA-Workspace-ID` as a synonym for `X-DSA-Session-ID` for one minor version; add a deprecation log on the alias path; preserve existing single-source SessionContext behavior

### Workspace registry (per-tab in-memory)

- [ ] T014 Create `src/platform_agent/workspace/registry.py` — `WorkspaceRegistry` keyed by per-tab UUID, holding `Workspace` records with their `connections[]`; thread-safe; in-memory only (Q1, R1)
- [ ] T015 Create `src/platform_agent/workspace/multi_source_driver.py` — `MultiSourceDriver` that holds a registry of `DatabaseDriver` instances per `connection_id` and routes `scan_metadata` / `run_query` based on a fully-qualified `source.schema.table` reference (plan.md project structure)

### Driver: Iceberg/Glue (new — required by US1 and downstream)

- [ ] T016 [P] Create `src/platform_agent/drivers/iceberg.py` — `IcebergDriver` implementing the existing `DatabaseDriver` protocol via `pyiceberg` + `boto3` Glue client; supports `connect`, `scan_metadata` (Glue `GetTables` + `Catalog.load_table`), `run_query` (pyiceberg `Table.scan()` with 250-row cap at scan layer), `dbt_config` (dbt-glue profile) (R3)
- [ ] T017 [P] Register `IcebergDriver` in `src/platform_agent/drivers/__init__.py` `DRIVER_REGISTRY` so `create_driver(driver_type="iceberg", ...)` resolves
- [ ] T018 [P] Contract test: `tests/contract/test_iceberg_driver.py` — covers connect/scan/query/dbt_config against either a moto-glue stub or a recorded fixture; verifies SELECT/WITH-only enforcement and the 250-row cap

### Per-connection durable store (Q2, R2)

- [ ] T019 Create `src/platform_agent/semantic/store.py` — `ConnectionStore` Protocol + `make_store(connection_id)` factory selecting local vs deployed via `STORAGE_BACKEND` env
- [ ] T020 Create `src/platform_agent/semantic/store_local.py` — SQLite-backed store at `~/.dsa-hub/connections/<connection_id>/store.db` with tables `entities`, `attributes`, `metrics`, `joins`, `physical_bindings`, `products`, `activity_log`, `discovery_cache`; transactions per write (R2)
- [ ] T021 Create `src/platform_agent/semantic/migrations/__init__.py` + `001_initial.py` — alembic-style schema migration framework for the SQLite store; runs on first open
- [ ] T022 [P] Create `src/platform_agent/semantic/store_deployed.py` — DynamoDB single-table `DSAHubConnectionStore` (PK `connection_id`, SK `entity_kind#entity_id`) with sparse GSI on `(connection_id, kind)`; idempotent put/get/list; honors the same Protocol (R2)
- [ ] T023 [P] Add Terraform definition for the DynamoDB table in `infra-terraform/modules/data/main.tf` (deployed-mode only; local mode skips); plus IAM policy fragment for runtime access
- [ ] T024 [P] Contract test: `tests/contract/test_connection_store.py` — exercises both backends behind the Protocol; covers entity CRUD, joins, products, activity log append-only invariant (data-model.md §3 invariants)

### `connection_id` derivation

- [ ] T025 Add `src/platform_agent/workspace/connection_id.py` — `derive_connection_id(driver_type, endpoint, scope) -> str` returning a stable SHA-256 (R2); unit-tested with property tests for stability across argument-order normalization

### Activity log writer

- [ ] T026 Create `src/platform_agent/workspace/activity_log.py` — append-only writer that takes `(connection_id, kind, payload)` and writes through the connection's store; never raises into the caller (logs+drops on store failure to preserve user-flow invariants)

### Bootstrap script + Pinnacle seeds (FR-042, R11)

- [ ] T027 Replace `scripts/seed_northwinds.sql` with `scripts/seed_pinnacle.sql` containing the 8 business processes at named row volumes (data-model.md §8 + R11); idempotent (`CREATE TABLE IF NOT EXISTS`, `ON CONFLICT DO NOTHING`); a final sanity-count `SELECT` block prints the eight totals
- [ ] T028 Update `scripts/bootstrap.sh` to invoke `seed_pinnacle.sql` (not `seed_northwinds.sql`); rename existing references; preserve Redshift seed handling (Redshift is not in the v1 demo path but must continue to bootstrap successfully for regression)
- [ ] T029 [P] Add `scripts/seed_pinnacle_snowflake.sql` — analytical mirror with shared business keys (`client_id`, `account_id`, `strategy_id`); add a tiny `python -m platform_agent.scripts.apply_snowflake_seed` driver in `src/platform_agent/scripts/apply_snowflake_seed.py` invoking SnowflakeDriver via SSO

### ADRs (in-flight per Addendum E)

- [ ] T030 [P] Author `docs/adr/016-multi-connection-workspace.md` recording Q1 (per-tab/session) decision; landed in the same commit as T013/T014
- [ ] T031 [P] Author `docs/adr/017-per-connection-semantic-graph.md` recording Q2 + R2 (per-connection store, SQLite local / DynamoDB deployed); landed in the same commit as T019/T020
- [ ] T031a [P] Author **initial** `docs/adr/020-provisioning-orchestration-iceberg.md` (Iceberg driver decision only — R3); landed in the same commit as T016. The orchestration + validation-threshold + palette portions of the decision (R6 + R8 + R10) are added as an amendment in Phase 5 (T090). This split keeps Addendum E's "ADR lands with the decision" invariant intact, since the IcebergDriver decision physically commits in Phase 2.

**Checkpoint**: Foundation ready — every user story phase below can now begin in parallel (subject to team capacity).

---

## Phase 3: User Story 1 — Multi-source connection hub (Priority: P1) 🎯 MVP

**Goal**: A DSA can add 2 sources to a per-tab workspace and see both reach `live` with KPI tiles ticking; lens selector exposes "all" plus per-source. (spec.md §US1)

**Independent Test**: Add a Postgres + a Snowflake connection on a fresh workspace; both cards reach `live`; KPI strip reflects merged totals; lens selector lists "all" + each connection.

### Contract tests for US1

- [ ] T032 [P] [US1] Contract test: `tests/contract/test_workspace_connections.py` — exercises `POST /workspace/connection`, `GET /workspace/connections`, `DELETE /workspace/connection/{id}`, `POST /workspace/connection/{id}/retry`, `GET /workspace/kpis` per `contracts/workspace.openapi.yaml`; covers 201/400/409/204/404; verifies state machine transitions (connecting → scanning → live)
- [ ] T033 [P] [US1] Integration test: `tests/integration/test_workspace_lifecycle.py` — adds 2 mock connections, asserts kpi merge and lens list; asserts duplicate `(driver_type, endpoint, scope)` is a 409
- [ ] T034 [P] [US1] Cascade-regression test: extend `tests/integration/test_session_alias.py` to verify a request with `X-DSA-Session-ID` only (no workspace header) routes to single-source path identically to pre-feature behavior (SC-007)

### Backend implementation for US1

- [ ] T035 [US1] Create `src/platform_agent/api/routes_workspace.py` implementing all endpoints in `contracts/workspace.openapi.yaml`; uses `WorkspaceRegistry` (T014) + `MultiSourceDriver` (T015) + `derive_connection_id` (T025)
- [ ] T036 [US1] Wire `routes_workspace` into `src/platform_agent/api/app.py` lifespan + router list
- [ ] T037 [US1] Implement connection lifecycle worker in `src/platform_agent/workspace/lifecycle.py` — async transitions `connecting → scanning → live` (calls driver.connect → scan_metadata) with KPI tile updates; error path with `retryable` classification
- [ ] T038 [US1] Activity-log emission for `connection_added`, `connection_error`, `connection_retried` (uses T026)

### Frontend implementation for US1

- [ ] T039 [P] [US1] Create `frontend/src/routes/Connections.tsx` (route `/connections`) — card grid + Add Connection CTA + workspace KPI strip (FR-003, FR-004)
- [ ] T040 [P] [US1] Create `frontend/src/components/workspace/ConnectionCard.tsx` — driver label, schema/db count, table count, last-synced ts, status pulse, per-source KPI tiles (rows scanned, tables profiled, processes detected)
- [ ] T041 [P] [US1] Create `frontend/src/components/workspace/AddConnectionModal.tsx` — driver-specific forms for postgresql/redshift/snowflake/databricks/iceberg with field hints + secret-handling note
- [ ] T042 [P] [US1] Create `frontend/src/components/workspace/WorkspaceKPIStrip.tsx` — animated counters (sources / tables / rows / processes / semantic entities) per US1 acceptance #1
- [ ] T043 [P] [US1] Create `frontend/src/hooks/useWorkspace.ts` — workspace state + connection CRUD with optimistic updates + SSE/poll for status transitions
- [ ] T044 [US1] Extend `frontend/src/context/AppContext.tsx` to carry `workspaceId`, `connections[]`, `activeLens` and a `lensOptions` derived list (default `"all"` once ≥2 connections live)
- [ ] T045 [US1] Update `frontend/src/lib/session.ts` to expose `workspaceId` alongside the existing `sessionId` (same UUID)
- [ ] T046 [US1] Extend `frontend/src/components/shell/ContextBar.tsx` to render the workspace switcher + active-lens selector (FR-005)

**Checkpoint**: A DSA can fully drive `/connections` with two real sources; KPI strip animates as each goes live; lens selector populates. **MVP is shippable here even without the rest.**

---

## Phase 4: User Story 2 — Discovery + Pilled PRDs on Step 1 (Priority: P1)

**Goal**: After both Pinnacle sources are connected, Step 1 shows 8 process cards + cross-source coverage matrix + ≥6 schema-grounded pills; clicking a pill opens Step 2 with a pre-drafted cross-source PRD targeting an Iceberg table. (spec.md §US2)

**Independent Test**: With both Pinnacle sources live, navigate to Step 1; assert 8 cards present (named per FR-008), matrix shows ≥3 cross-source overlaps, ≥6 pills offered. Click "Client 360" pill → Step 2 opens with PRD containing target, joins, and ≥1 business question.

### Contract tests for US2

- [ ] T047 [P] [US2] Contract test: `tests/contract/test_discover_workspace.py` — exercises both `scope=connection` and `scope=workspace` per `contracts/discover.openapi.yaml`; verifies for the seeded Pinnacle Postgres the 8 named processes are present (FR-008) and the matrix has the expected cross-source rows
- [ ] T048 [P] [US2] Contract test: `tests/contract/test_pills.py` — exercises `POST /workflow/pills` and `POST /workflow/pills/{pill_id}/draft-prd` per `contracts/pills.openapi.yaml`; asserts ≥6 pills (FR-011), every `target_iceberg_table` matches the regex, and `seed_prd_body.standards_applied` is non-empty (SC-011)
- [ ] T049 [P] [US2] Eval case set: `eval/test_cases/pill_agent.json` — ≥8 cases covering Pinnacle (must produce the six named pills) + a non-Pinnacle dataset (SC-010 — pills reflect the alternate schema)

### Backend implementation for US2

- [ ] T050 [US2] Extend `src/platform_agent/api/routes_discover.py` to accept the workspace-scoped variant; merge per-connection discovery cache snapshots into a `CoverageMatrix` (R2 + data-model.md §9); shared-key detection runs on common attribute names (`client_id`, `account_id`, `strategy_id`, …) — schema-driven, not hardcoded
- [ ] T051 [P] [US2] Create `src/platform_agent/tools/standards_read.py` — `@tool` exposing the read-only Standards content (used by Step 1 PRD draft to populate `standards_applied`); reads from `src/platform_agent/standards/` (content created in Phase 9 but tool stubs the file-not-found case to "" gracefully)
- [ ] T052 [US2] Create `src/platform_agent/tools/pill_generator.py` — `@tool` invoked by the pill-agent; returns ≥`min_pills` pill suggestions; uses the discovery summaries + coverage matrix as input (R5)
- [ ] T053 [US2] Create `src/platform_agent/prompts/pill_agent.md` — Strands system prompt with the six Pinnacle pills as in-context few-shot examples (R5); explicit instruction that pills MUST be schema-grounded and MUST declare an Iceberg target FQN
- [ ] T054 [US2] Create `src/platform_agent/api/routes_pills.py` implementing both endpoints from `contracts/pills.openapi.yaml`; routes through a Strands agent created via `create_agent("pill_agent", model="opus-4.7")` (R5)
- [ ] T055 [US2] Wire `routes_pills` into `app.py`
- [ ] T056 [US2] Extend `src/platform_agent/workflow/step_1_requirements.py` so a `pill_id` query param skips the freeform PRD path and instead reuses the pill's `seed_prd_body`; standards footer is appended via `standards_read` (FR-038, SC-011)
- [ ] T057 [US2] Activity-log emission for `discovery_completed` and `pill_clicked` (T026)

### Frontend implementation for US2

- [ ] T058 [P] [US2] Create `frontend/src/routes/Step1Discovery.tsx` — replaces today's Step 1; renders KPI strip, ProcessCard list, CoverageMatrix, PillRow
- [ ] T059 [P] [US2] Create `frontend/src/components/discovery/ProcessCard.tsx` — name + domain icon + source backings + volume signal (row count + dollar total) + last-activity timestamp + sparkline (FR-009)
- [ ] T060 [P] [US2] Create `frontend/src/components/discovery/CoverageMatrix.tsx` — process × connection grid; ready-to-combine cells highlighted (FR-010)
- [ ] T061 [P] [US2] Create `frontend/src/components/discovery/PillRow.tsx` — pill chips with title / subtitle / icon / estimated minutes; click-to-PRD handoff
- [ ] T062 [P] [US2] Create `frontend/src/hooks/usePills.ts` and `frontend/src/hooks/useSourceDiscovery.ts` (extend existing) for per-connection + workspace-level discovery; cache keyed by workspace + force flag
- [ ] T063 [US2] Wire pill click → navigate to `/workflow/step2?pill_id=...`; Step 2 reads `pill_id`, calls `/workflow/pills/{id}/draft-prd`, opens with the seeded PRD
- [ ] T064 [US2] Update `frontend/src/hooks/useAgent.demo.ts` with the canned Pinnacle multi-source scenario (FR-041, R9): pre-staged Iceberg connection, 2 source connections going live with seeded KPI counts, 8 process cards, 6 demo pills, scripted Build-page run

### ADR

- [ ] T065 [P] [US2] Author `docs/adr/021-pill-generation.md` recording R5 (schema-driven, Opus 4.7, few-shot Pinnacle examples); landed in the same commit as T053/T054

**Checkpoint**: A DSA on Step 1 sees 8 Pinnacle process cards + 6 pills; clicking Client 360 opens Step 2 with a complete cross-source PRD draft.

---

## Phase 5: User Story 3 — Provisioning DAG into Iceberg (Priority: P2)

**Goal**: PRD acceptance kicks off a 7-agent provisioning run with live DAG, KPI tiles, and streaming activity log; terminates with a registered Iceberg Data Product (final or provisional per Q5). (spec.md §US3)

**Independent Test**: Accept any drafted PRD with a live Iceberg connection in the workspace; Build page renders <2s; all 7 agents reach a terminal state; the Iceberg table is registered and (if pass rate ≥80%) queryable from TTYD.

### Contract tests for US3

- [ ] T066 [P] [US3] Contract test: `tests/contract/test_provision.py` — exercises `POST /workflow/provision` (201, 400 for `redundancy_not_cleared` / `no_iceberg_target` / `read_only_violation` / `prd_invalid`), `GET /workflow/provision/{run_id}`, `POST /workflow/provision/{run_id}/retry` per `contracts/provision.openapi.yaml`
- [ ] T067 [P] [US3] Contract test: `tests/contract/test_provision_sse_v2.py` — opens an SSE stream against a stub run, asserts every event carries the v2 envelope `{run_id, seq, ts, v: 2}` and that `agent.started → agent.progress* → agent.completed | agent.failed` ordering holds
- [ ] T068 [P] [US3] Integration test: `tests/integration/test_provisioning_dag.py` — full end-to-end run with stub agents asserting state machine transitions (queued → running → {completed | needs_replan | failed}) and per-agent retry semantics (FR-029)

### Promote migration-suite agents into the in-product orchestrator

- [ ] T069 [P] [US3] Move `patterns/migration-agent/tools/extract_schema.py` → `src/platform_agent/provisioning/agents/schema_agent.py`; preserve I/O contracts; add Strands `@tool` decorators where missing; leave `patterns/` files in place as legacy reference per Complexity Tracking row 3
- [ ] T070 [P] [US3] Move pipeline behavior to `src/platform_agent/provisioning/agents/pipeline_agent.py` — runs the per-source pulls + DuckDB scratchpad write into staging Parquet (foundation for the mapping-agent step)
- [ ] T071 [P] [US3] Move dbt scaffolding from `patterns/migration-agent/tools/scaffold_dbt_project.py` → `src/platform_agent/provisioning/agents/model_agent.py`; targets dbt-glue for Iceberg
- [ ] T072 [P] [US3] Move `patterns/quality-agent/tools/quality_rules.py` + `quarantine.py` → `src/platform_agent/provisioning/agents/quality_agent.py`; runs dbt test + DQDL rules
- [ ] T073 [P] [US3] Move `patterns/migration-agent/tools/convert_to_iceberg.py` + `validate_migration.py` → `src/platform_agent/provisioning/agents/mapping_agent.py`; this agent owns Glue table registration via the `IcebergDriver`

### New agents

- [ ] T074 [P] [US3] Create `src/platform_agent/provisioning/agents/semantic_agent.py` — writes the new entities, attributes, metrics, joins, and physical bindings into the **target connection's** store via the `ConnectionStore` Protocol (T019); idempotent on rerun
- [ ] T075 [P] [US3] Create `src/platform_agent/provisioning/agents/delivery_agent.py` — flips `ttyd_exposed` based on validation pass rate; triggers auto-validation; writes activity-log entries `product_registered`, `product_promoted`
- [ ] T076 [P] [US3] Create `src/platform_agent/prompts/semantic_agent.md` and `src/platform_agent/prompts/delivery_agent.md` system prompts (R6 + R8)

### Orchestrator + SSE

- [ ] T077 [US3] Create `src/platform_agent/provisioning/orchestrator.py` — DAG runner with the dependency edges from R6 (`schema → pipeline → model → quality → mapping → {semantic, delivery}`); per-agent retry that reuses upstream artifacts cached by `run_id` (FR-029)
- [ ] T078 [US3] Create `src/platform_agent/provisioning/events.py` — extends `src/platform_agent/api/events.py` with the v2 envelope and the 11 new event kinds in `contracts/provision.openapi.yaml` (`agent.started/progress/completed/failed`, `kpi.tick`, `artifact.produced`, `validation.started/result`, `run.completed`, `run.needs_replan`, `heartbeat`)
- [ ] T079 [US3] Create `src/platform_agent/api/routes_workflow_provision.py` (or extend existing `routes_workflow.py`) implementing the three endpoints from `contracts/provision.openapi.yaml`; wires through `SSEEmitter` (existing) with passive 10s heartbeat
- [ ] T080 [US3] Iceberg-target-presence guard at `POST /workflow/provision`: rejects with `400 no_iceberg_target` if workspace contains no live `driver_type=iceberg` connection (FR-031, Q3)
- [ ] T081 [US3] Validation threshold logic in `delivery_agent` reads `DSA_HUB_VALIDATION_THRESHOLD` env (default 0.80); writes `IcebergDataProduct.state = final | provisional`; flips `ttyd_exposed` atomically (R8)

### Frontend implementation for US3

- [ ] T082 [P] [US3] Create `frontend/src/routes/Build.tsx` (route `/build/:run_id`) — hosts AgentDAG + BuildKPIStrip + ActivityStream + ValidationCard
- [ ] T083 [P] [US3] Create `frontend/src/components/build/AgentDAG.tsx` — React Flow graph with the 7 agent nodes + dependency edges; pulse on active, ✓ on complete with artifact summary, amber/retry on failed (FR-028, US-3 acceptance #2: <1s state-update latency)
- [ ] T084 [P] [US3] Create `frontend/src/components/build/BuildKPIStrip.tsx` — rows in motion / agents active / latency p95 / files written / est cost / ETA; SSE-driven (FR-030)
- [ ] T085 [P] [US3] Create `frontend/src/components/build/ActivityStream.tsx` — timestamped log entries with agent name + badge + message + code spans for object names
- [ ] T086 [P] [US3] Create `frontend/src/hooks/useProvisioningRun.ts` — subscribes to `/workflow/provision/{run_id}/events`; maps v2 events into in-memory `ProvisioningRunState`
- [ ] T087 [US3] Build out `frontend/src/lib/agentcore-client/parsers/v2/index.ts` — extends v1 with the 11 new event kinds; version-gated by `v: 2` envelope field (R6)
- [ ] T088 [US3] Wire Step 4's "Accept & provision" CTA to `POST /workflow/provision`; on 201 navigate to `/build/<run_id>`; on `400 no_iceberg_target` surface an "Add Iceberg target connection" modal (FR-031 edge case)

### Color palette extension (R10, Constitution Article V)

- [ ] T089 [P] [US3] Add CSS custom properties `--status-success: #16A34A` and `--status-error: #DC2626` to `frontend/src/index.css` (or theme file); document the two-role-only constraint in a code comment + the ADR; verify no other off-brand colors land in this commit

### ADR

- [ ] T090 [P] [US3] **Amend** `docs/adr/020-provisioning-orchestration-iceberg.md` (initial Iceberg-driver-only stub created in T031a) with the orchestration + validation threshold + palette extension portions: R6 (orchestrator design + SSE v2), R8 (validation threshold gate at 80% with provisional/final state machine), R10 (status-success / status-error palette additions). Landed in the same commit as T077/T079.

**Checkpoint**: PRD acceptance produces a streaming DAG run terminating in a registered Iceberg Data Product (final or provisional).

---

## Phase 6: User Story 4 — Cross-Source Talk-to-Data (Priority: P2)

**Goal**: With lens=`all` and ≥2 live connections, TTYD plans single-source vs cross-source, executes with a DuckDB scratchpad, and returns answers with per-source chips + scratchpad chip + semantic-hit chips. (spec.md §US4)

**Independent Test**: Ask a question requiring both Pinnacle sources; response shows ≥2 per-source chips + a scratchpad/join chip + sensible answer; per-source pulls capped at 250 rows; joined result capped at 5,000 rows; truncations explicit.

### Contract tests for US4

- [ ] T091 [P] [US4] Contract test: `tests/contract/test_query_cross_source.py` — exercises `POST /workflow/query` per `contracts/ttyd-cross-source.openapi.yaml`; asserts 200 happy path, `400 cross_source_unavailable` when lens=all but <2 live connections, `400 read_only_violation` for write-keyword attempts (FR-018, SC-006)
- [ ] T092 [P] [US4] Integration test: `tests/integration/test_duckdb_scratchpad.py` — registers two pandas-like row sets as DuckDB views, runs a join, asserts the 5,000-row cap is enforced + truncated_at_cap flag set when exceeded

### Backend implementation for US4

- [ ] T093 [P] [US4] Create `src/platform_agent/tools/duckdb_scratchpad.py` — `@tool cross_source_query(per_source_pulls, join_sql) -> Result`; one DuckDB session per turn, disposed at end; SELECT/WITH-only enforcement on `join_sql`; per-source pull cap 250, joined cap 5,000; truncation flags surfaced in result (R4)
- [ ] T094 [US4] Create `src/platform_agent/tools/cross_source_query.py` — high-level planner tool: classifies one-source vs cross-source from the question + lens + workspace state; invokes `duckdb_scratchpad` only for cross-source; consults the relevant connection's semantic graph (FR-019)
- [ ] T095 [US4] Extend `src/platform_agent/api/routes_query.py` with the cross-source path; the planner is gated to `lens=all` AND ≥2 live connections per FR-015; `target_product_id` short-circuits to a single-source query against the Iceberg connection holding the product
- [ ] T096 [US4] TTYD response shape: build `sources_used`, `semantic_hits`, and `kpi_snapshot` per `contracts/ttyd-cross-source.openapi.yaml`
- [ ] T097 [US4] Activity-log emission for cross-source TTYD turns using kind `ttyd_query` (already enumerated in T012); records `(question, lens, sources_used[].connection_id, latency_ms)` payload

### Frontend implementation for US4

- [ ] T098 [P] [US4] Create `frontend/src/components/chat/SourceChips.tsx` — render `sources_used` as chips (driver icon + scope + row count) + a 🦆 DuckDB join chip when present; per-step SQL collapsibles for each chip
- [ ] T099 [P] [US4] Create `frontend/src/components/chat/TtydKPIBar.tsx` — queries answered / avg latency / sources used today / semantic-hit rate (FR-020)
- [ ] T100 [US4] Wire SourceChips + TtydKPIBar into the existing TTYD response renderer in `frontend/src/components/artifact/TalkToData.tsx`
- [ ] T101 [US4] Read-only enforcement at the UI: client-side regex pre-check on user-typed SQL escapes (defense-in-depth; backend remains authoritative); friendly error toast on attempted writes

### ADR

- [ ] T102 [P] [US4] Author `docs/adr/018-cross-source-query-via-duckdb.md` recording R4; landed in the same commit as T093/T094

**Checkpoint**: A DSA can ask cross-source questions and see the full execution trail in the response.

---

## Phase 7: User Story 5 — Per-Connection Semantic Graphs (Priority: P3)

**Goal**: Each connection has its own semantic graph; the Semantic page lets the DSA browse graphs per connection and inspect entity/metric/binding details. No cross-connection reconciliation in v1 (Q2). (spec.md §US5)

**Independent Test**: After a successful provisioning run, switch to the target Iceberg connection on the Semantic page; ≥1 entity present with ≥1 binding; switch to a source connection and see *its* graph independently.

### Contract tests for US5

- [ ] T103 [P] [US5] Contract test: `tests/contract/test_semantic_graph.py` — exercises `GET /semantic/graph?connection_id=...` (with optional `domain` filter) and `GET /semantic/entities/{entity_id}` per `contracts/semantic.openapi.yaml`; asserts 404 for unknown connection_id

### Backend implementation for US5

- [ ] T104 [US5] Create `src/platform_agent/tools/semantic_graph_read.py` — `@tool` used by both this route and the redundancy-agent (US6); reads through `ConnectionStore` (T019)
- [ ] T105 [US5] Create `src/platform_agent/tools/semantic_graph_write.py` — `@tool` used by `semantic_agent` (T074); never called by user-facing routes (FR-025 enforces no public write endpoint)
- [ ] T106 [US5] Create `src/platform_agent/api/routes_semantic.py` implementing the two endpoints from `contracts/semantic.openapi.yaml`; computes `kpi_strip` (entities/metrics/joins/bindings/processes_mapped_pct) on the fly
- [ ] T107 [US5] Wire `routes_semantic` into `app.py`

### Frontend implementation for US5

- [ ] T108 [P] [US5] Create `frontend/src/routes/Semantic.tsx` (route `/semantic`) — connection switcher + per-connection KPI strip + force-directed graph + filter-by-domain + entity side panel
- [ ] T109 [P] [US5] Create `frontend/src/components/semantic/SemanticGraph.tsx` — React Flow force-directed view; entities as nodes, joins as edges (FR-024)
- [ ] T110 [P] [US5] Create `frontend/src/components/semantic/EntityPanel.tsx` — attributes + metrics + physical bindings detail (FR-024)
- [ ] T111 [P] [US5] Create `frontend/src/hooks/useSemanticGraph.ts` — fetches per-connection graph, exposes connection switcher state, applies domain filter

**Checkpoint**: Per-connection graphs visible and navigable; no cross-connection overlay (per Q2).

---

## Phase 8: User Story 6 — Redundancy Gate + Auto-Validation (Priority: P3)

**Goal**: Before acceptance, a redundancy report against the target connection's graph blocks/permits proceed; after provisioning, a Validation Card auto-runs PRD questions and reports ✓/✗ per question with re-plan affordance. (spec.md §US6)

**Independent Test (redundancy)**: Draft a PRD that overlaps an existing entity — gate returns `partial_overlap` with reuse-or-override card. Draft a fully-novel PRD — gate returns `net_new` and proceeds.
**Independent Test (validation)**: Complete a provisioning run; Validation Card auto-runs each PRD business question; ≥80% pass → product `final`; <80% → product `provisional` and "Re-plan" affordance available.

### Contract tests for US6

- [ ] T112 [P] [US6] Contract test: `tests/contract/test_redundancy.py` — exercises `POST /workflow/redundancy-check` and `POST /workflow/redundancy-check/{report_id}/decide` per `contracts/redundancy.openapi.yaml`; asserts blocking semantics on `duplicate` without override rationale (FR-026)
- [ ] T113 [P] [US6] Integration test: `tests/integration/test_validation_threshold.py` — runs provisioning with a stub `delivery-agent` LLM-as-judge that produces controllable pass rates; asserts at 100/80/79/0% the product state and `ttyd_exposed` flip behaviors (R8)
- [ ] T114 [P] [US6] Eval case sets: `eval/test_cases/redundancy_agent.json` (≥6 cases: net-new / partial / duplicate / fuzzy match) and `eval/test_cases/delivery_agent.json` (≥6 cases: passing / failing / mixed validation results)

### Redundancy implementation

- [ ] T115 [P] [US6] Create `src/platform_agent/tools/redundancy_check.py` — `@tool` invoked by the redundancy-agent; reads target connection graph via `semantic_graph_read` (T104); returns overlap percentage + side-by-side diff per `contracts/redundancy.openapi.yaml#OverlapItem`
- [ ] T116 [P] [US6] Create `src/platform_agent/prompts/redundancy_agent.md` — Strands system prompt for `redundancy-agent` (Opus 4.7 per R7)
- [ ] T117 [US6] Create `src/platform_agent/api/routes_redundancy.py` implementing both endpoints; gates `provision` on a cleared report (FR-026)
- [ ] T118 [US6] Wire `routes_redundancy` into `app.py`

### Validation flow

- [ ] T119 [US6] Validation engine in `delivery_agent` (extends T075): for each `prd.business_questions`, formulate via TTYD planner (lens=`all`), run, evaluate via LLM-as-judge (Opus 4.7), record `ValidationResult`; aggregate pass rate (R8)
- [ ] T120 [US6] Provisioning rerun semantics: `POST /workflow/provision/{run_id}/retry` with `agent_id="validation"` re-runs only validation; promotes provisional → final atomically when pass rate ≥ threshold (FR-035, R8)

### Frontend implementation for US6

- [ ] T121 [P] [US6] Create `frontend/src/components/gates/RedundancyGate.tsx` — modal between Step 1 and Step 2 (Step 4 in the current numbering) showing report state + per-overlap reuse-or-override cards + override-rationale field for `duplicate`
- [ ] T122 [P] [US6] Create `frontend/src/components/build/ValidationCard.tsx` — rendered on Build page bottom; per-question spinner → ✓/✗ with SQL + result preview on click; "Re-run from failed step" affordance on <threshold runs (FR-034, FR-035). Includes the FR-036 validation KPI strip at the card header: `questions auto-validated`, `% passing`, `avg query latency (ms)`, `semantic-layer hit rate`, `Iceberg scan bytes` — sourced from the run's `validation_results[]` + `kpi_series[]` (see `provision.openapi.yaml#KpiTick`).
- [ ] T123 [P] [US6] Create `frontend/src/hooks/useRedundancyCheck.ts` — calls `POST /workflow/redundancy-check`, holds report state, posts decisions
- [ ] T124 [US6] Wire RedundancyGate before `POST /workflow/provision`; pass cleared `report_id` into the provision payload

### ADR

- [ ] T125 [P] [US6] Author `docs/adr/019-redundancy-gate.md` recording R7; landed in the same commit as T115/T117

**Checkpoint**: Pre-acceptance redundancy gate active; post-provisioning validation card closes the prove-it loop.

---

## Phase 9: User Story 7 — Standards Page (Priority: P3)

**Goal**: Read-only browser of naming, metric, PII, dbt, domain, Iceberg standards; PRDs include a "Standards applied" footer. (spec.md §US7)

**Independent Test**: `/standards` shows all six categories populated; every generated PRD ends with a non-empty footer (SC-011).

### Standards content

- [ ] T126 [P] [US7] Create `src/platform_agent/standards/` directory with one Markdown file per category: `naming.md`, `metrics.md`, `pii_policy.md` (informational only per Q4), `dbt_templates.md`, `domains.md` (Pinnacle: `wealth_mgmt`, `accounting`, `crm`, `hr`, `planning`), `iceberg_standards.md` (partitioning, sort orders, retention)
- [ ] T127 [P] [US7] Update `src/platform_agent/tools/standards_read.py` (stub from T051) to fully resolve content from `standards/` and join in approved metrics from per-connection semantic graphs

### Backend implementation for US7

- [ ] T128 [US7] Create `src/platform_agent/api/routes_standards.py` — read-only `GET /standards` and `GET /standards/{category}` endpoints; no contract test file needed (small surface; covered by integration test T129)
- [ ] T129 [P] [US7] Integration test: `tests/integration/test_standards_footer.py` — generates a PRD via `step_1_requirements` and asserts the resulting `standards_applied` list is non-empty (SC-011, FR-038)
- [ ] T130 [US7] Wire `routes_standards` into `app.py`

### Frontend implementation for US7

- [ ] T131 [P] [US7] Create `frontend/src/routes/Standards.tsx` (route `/standards`) — sectioned read-only browser
- [ ] T132 [P] [US7] Create `frontend/src/components/standards/StandardsBrowser.tsx` — category sidebar + Markdown content rendering

**Checkpoint**: Standards visible; PRD footers populated.

---

## Phase 10: Polish & Cross-Cutting Concerns

**Purpose**: Regression, performance, eval, docs, final ADR review.

### Regression

- [ ] T133 Run full pytest suite (`uv run pytest`) — all 51 existing + every new contract/integration/unit test added in this feature must pass (SC-007)
- [ ] T134 Run vitest cascade-invalidation suite (`pnpm test`) — all pre-existing tests pass; no flakes attributable to multi-source rework (SC-007)
- [ ] T135 Run `uv run mypy src/platform_agent/workspace src/platform_agent/provisioning src/platform_agent/semantic` in strict mode and resolve all errors (Constitution Article III)
- [ ] T136 Run `uv run ruff check src/ tests/ patterns/ frontend/scripts/` and `uv run ruff format src/ tests/ patterns/`

### Performance verification

- [ ] T137 [P] Verify SC-002 — second-connection-live → 8 process cards within 60s on the seeded Pinnacle Postgres
- [ ] T138 [P] Verify SC-005 — cross-source TTYD answers within 5s on a question requiring both seeded sources
- [ ] T139 [P] Verify US-3 acceptance #2 — agent state transitions render within 1s of the underlying state change (browser dev tools timeline)
- [ ] T140 [P] Verify US-6 acceptance #4 — each PRD business question resolves within 30s of provisioning completion
- [ ] T141 Verify SC-001 — full Pinnacle showcase narrative completes within 8 minutes live (timed walk-through; record in `specs/002-dsa-hub-pinnacle/quickstart.md` §6 demo log section)

### Eval

- [ ] T142 [P] Run all eval cases: `uv run python -m platform_agent.eval pill-agent redundancy-agent semantic-agent delivery-agent` — every case passes or has a logged-known-bad note

### Demo mode

- [ ] T143 Verify SC-009 — `DSA_HUB_DEMO_MODE=1` reproduces the full multi-source narrative offline (no AWS/DB calls); spot-check that the seven-agent DAG, validation card, and TTYD responses all render with deterministic timing

### Docs

- [ ] T144 [P] Update `CLAUDE.md` Active Technologies + Recent Changes sections with the feature; refresh the Directory Layout block to reflect promoted patterns + new modules (`workspace/`, `provisioning/`, `semantic/`, new routes, new tools, Iceberg driver)
- [ ] T145 [P] Update `README.md` Quick Start to point at `scripts/seed_pinnacle.sql` and the three-frontend launch flow; add a one-paragraph blurb on the multi-source hub
- [ ] T146 [P] Verify all six ADRs (016–021) are committed and cross-referenced from `plan.md` + the relevant code modules

### Final regression checkpoint

- [ ] T147 Walk through `quickstart.md` end-to-end on a fresh checkout (clean `~/.dsa-hub/`) — every command in §1–§9 executes successfully; troubleshooting items §10 trigger as documented when forced

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: no dependencies — start immediately.
- **Phase 2 (Foundational)**: depends on Phase 1; **blocks all user stories**.
- **Phase 3 (US1)**: depends on Phase 2 only.
- **Phase 4 (US2)**: depends on Phase 2 + (functionally) Phase 3 — discovery + pills are reachable only via the Connections page, but US2 backend tasks can begin in parallel with US1 frontend tasks.
- **Phase 5 (US3)**: depends on Phase 2 + Phase 4 (US3 needs a PRD to provision; the PRD path is wired in US2). Backend orchestrator tasks (T077–T081) can begin in parallel with US1/US2 frontend work.
- **Phase 6 (US4)**: depends on Phase 2 only — cross-source TTYD does not depend on US3's provisioning being complete; it just needs ≥2 live connections.
- **Phase 7 (US5)**: depends on Phase 2 + Phase 5 (semantic graphs are populated by the semantic-agent during provisioning).
- **Phase 8 (US6)**: depends on Phase 5 (validation runs inside provisioning) + Phase 7 (redundancy reads the semantic graph).
- **Phase 9 (US7)**: depends on Phase 2 only — content authoring + read-only routes; PRD footer wiring touches Step 1 (already extended in Phase 4 via T056).
- **Phase 10 (Polish)**: depends on all desired user-story phases being complete.

### User Story Dependencies (architecture-driven)

```
US1 (P1) ─┬─→ US2 (P1) ─→ US3 (P2) ─┬─→ US7 (validation card needs a run)
          │                          ├─→ US5 (semantic graph populated by US3)
          │                          └─→ US6 (validation lives inside US3; redundancy reads US5)
          └─→ US4 (P2) — needs ≥2 connections; independent of US3
US7 (P3, Standards content) — independent; runnable any time after Phase 2
```

### Parallel Opportunities

- **All Phase 1 tasks** can run in parallel.
- **All Phase 2 model tasks (T007–T012)** can run in parallel — different files.
- **Phase 2 driver/store tasks (T016–T024)** parallelize across driver vs store.
- **Within US1**: T032–T034 (tests) parallel; T039–T043 (frontend components) parallel.
- **Within US2**: T058–T062 (frontend components + hooks) parallel; T053 (prompt) + T052 (tool) + T054 (route) sequential within the agent path.
- **Within US3**: T069–T076 (agent file moves + new agents) all parallel; T083–T086 (frontend) parallel; T089 (palette) parallel with everything.
- **Within US4–US7**: most frontend component creation [P]; backend tools [P] when in different files.
- **All ADR tasks (T030, T031, T031a, T065, T090 [amend], T102, T125)** are [P] — different files (or different commits for the T031a/T090 amendment pair), paired with their implementing code commit per Addendum E.
- **Polish phase**: T137–T140 performance verifications and T142 eval can run in parallel; T143 demo mode is independent.

### Within Each User Story

- **Tests first** (every contract test marked [P]) — written and failing before the route lands per Spec/Constitution Article IX.
- **Models before services**: Pydantic shapes (Phase 2) are prerequisites; per-story tools/agents come next.
- **Tools before routes**: `@tool` files land before the FastAPI route that registers them.
- **Routes before frontend**: backend endpoint stable before the React hook that consumes it.
- **ADR with implementing commit**: Addendum E is non-negotiable — the ADR change rides with the commit that lands the decision.

---

## Parallel Execution Examples

### Phase 2 Foundational (largest parallelism window)

Example dispatch:

```text
# Pydantic models — six tasks, six different files
T007  workspace/models.py
T008  semantic/models.py
T009  workflow/discovery_models.py
T010  workflow/pill_models.py
T011  provisioning/models.py
T012  workspace/activity_models.py

# Driver + store work in parallel with models
T016  drivers/iceberg.py                (Iceberg driver impl)
T020  semantic/store_local.py           (SQLite store)
T022  semantic/store_deployed.py        (DynamoDB store)
T029  scripts/seed_pinnacle_snowflake.sql
```

### US1 Connections Page

```text
# Tests first, in parallel
T032  tests/contract/test_workspace_connections.py
T033  tests/integration/test_workspace_lifecycle.py
T034  tests/integration/test_session_alias.py

# Frontend components in parallel
T039  routes/Connections.tsx
T040  components/workspace/ConnectionCard.tsx
T041  components/workspace/AddConnectionModal.tsx
T042  components/workspace/WorkspaceKPIStrip.tsx
T043  hooks/useWorkspace.ts
```

### US3 Agent promotions (5 file-moves in parallel)

```text
T069  provisioning/agents/schema_agent.py
T070  provisioning/agents/pipeline_agent.py
T071  provisioning/agents/model_agent.py
T072  provisioning/agents/quality_agent.py
T073  provisioning/agents/mapping_agent.py
```

---

## Implementation Strategy

### MVP First (US1 only)

1. Complete Phase 1 + Phase 2 (Foundational — biggest investment).
2. Complete Phase 3 (US1 — multi-source connection hub).
3. **STOP and validate**: a DSA can add 2 connections and see the workspace KPI strip animate. That alone is a shippable demo of the new substrate.

### Incremental delivery

1. Setup + Foundational ⇒ foundation ready (no demo yet).
2. + US1 ⇒ multi-source workspace works (MVP demo).
3. + US2 ⇒ Pinnacle business-process discovery + pilled PRDs (the headline UX).
4. + US3 ⇒ live provisioning DAG into Iceberg.
5. + US4 ⇒ cross-source TTYD answers questions.
6. + US5 ⇒ Semantic page accumulates per-connection graphs.
7. + US6 ⇒ redundancy + auto-validation prove-it loop.
8. + US7 ⇒ Standards page enforces conventions on PRD footers.
9. Polish + regression ⇒ feature complete; SC-001 8-minute showcase rehearsable.

### Parallel team strategy

After Phase 2:

- Dev A: US1 + US2 (the discovery + pills user-facing path).
- Dev B: US3 (provisioning orchestrator + Build page).
- Dev C: US4 (cross-source TTYD + DuckDB scratchpad).
- Dev D (or Dev A after US2): US5 + US6 (semantic page + redundancy + validation card).
- Dev E (or part-time): US7 (standards content) + Phase 10 polish prep.

Each US is independently testable and rolls up cleanly through Polish.

---

## Notes

- **[P] = different files, no incomplete dependencies.**
- **Story labels** (`[USx]`) tie tasks to user stories for traceability; Setup, Foundational, and Polish phases carry no story label per Task Generation Rules.
- **Tests fail before implementation**: every contract test is committed in a state that fails against the as-yet-unimplemented route, per Article IX.
- **Commit boundaries**: each task or logical group commits independently. ADRs ride in the commit that lands the implementing code per Addendum E.
- **Avoid**: vague tasks, same-file conflicts, cross-story dependencies that break US independence, batched ADR commits.
- **Three-frontend rule** (Article II + CLAUDE.md): every UI surface introduced (Connections, Step 1 Discovery, Build, Semantic, Standards) must have a CLI text-mode equivalent. CLI tasks are intentionally *not* enumerated separately — each backend route lands a small `python -m platform_agent ...` subcommand alongside in the same task (e.g., `dsa-hub workspace add-connection`, `dsa-hub provision status <run_id>`, `dsa-hub semantic show --connection <id>`).
- **Streamlit alternate frontend**: continues to support single-source flows (FR-040). Multi-source UI is React-only in v1; Streamlit remains valid for the pre-existing Talk-to-Data demo.
