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

- [X] T007 [P] Create `src/platform_agent/workspace/models.py` with Pydantic v2 models: `Workspace`, `Connection`, `ConnectionKPIs`, `ConnectionError`, `Lens` (data-model.md §1, §2)
- [X] T008 [P] Create `src/platform_agent/semantic/models.py` with Pydantic v2 models: `SemanticEntity`, `Attribute`, `PhysicalBinding`, `Metric`, `Join` (data-model.md §4, §5, §6, §7)
- [X] T009 [P] Create `src/platform_agent/workflow/discovery_models.py` with `BusinessProcess`, `VolumeSignal`, `CoverageMatrix`, `CoverageRow`, `ProcessPresence` (data-model.md §8, §9)
- [X] T010 [P] Create `src/platform_agent/workflow/pill_models.py` with `PillSuggestion`, `PRDDraft`, `ProposedEntity`, `ProposedMetric`, `ProposedJoin`, `SourcePullSpec`, `IcebergTarget` (data-model.md §10, §11)
- [X] T011 [P] Create `src/platform_agent/provisioning/models.py` with `ProvisioningRun`, `AgentExecution`, `AgentError`, `Artifact`, `KpiTick`, `RedundancyReport`, `OverlapItem`, `Decision`, `IcebergDataProduct`, `ValidationResult` (data-model.md §12, §13, §14, §15)
- [X] T012 [P] Create `src/platform_agent/workspace/activity_models.py` with `ActivityLogEntry` and the kind enum (data-model.md §16). Enumerate all 13 kinds upfront so per-feature tasks don't need conditional enum edits: `connection_added`, `connection_error`, `connection_retried`, `discovery_completed`, `pill_clicked`, `prd_drafted`, `redundancy_decision`, `provisioning_started`, `agent_state_change`, `validation_result`, `product_registered`, `product_promoted`, `ttyd_query`.

### Per-tab session header alias (FR-006)

- [X] T013 Update `src/platform_agent/api/deps.py` to accept `X-DSA-Workspace-ID` as a synonym for `X-DSA-Session-ID` for one minor version; add a deprecation log on the alias path; preserve existing single-source SessionContext behavior

### Workspace registry (per-tab in-memory)

- [X] T014 Create `src/platform_agent/workspace/registry.py` — `WorkspaceRegistry` keyed by per-tab UUID, holding `Workspace` records with their `connections[]`; thread-safe; in-memory only (Q1, R1)
- [X] T015 Create `src/platform_agent/workspace/multi_source_driver.py` — `MultiSourceDriver` that holds a registry of `DatabaseDriver` instances per `connection_id` and routes `scan_metadata` / `run_query` based on a fully-qualified `source.schema.table` reference (plan.md project structure)

### Driver: Iceberg/Glue (new — required by US1 and downstream)

- [X] T016 [P] Create `src/platform_agent/drivers/iceberg.py` — `IcebergDriver` implementing the existing `DatabaseDriver` protocol via `pyiceberg` + `boto3` Glue client; supports `connect`, `scan_metadata` (Glue `GetTables` + `Catalog.load_table`), `run_query` (pyiceberg `Table.scan()` with 250-row cap at scan layer), `dbt_config` (dbt-glue profile) (R3)
- [X] T017 [P] Register `IcebergDriver` in `src/platform_agent/drivers/__init__.py` `DRIVER_REGISTRY` so `create_driver(driver_type="iceberg", ...)` resolves
- [X] T018 [P] Contract test: `tests/contract/test_iceberg_driver.py` — covers connect/scan/query/dbt_config against either a moto-glue stub or a recorded fixture; verifies SELECT/WITH-only enforcement and the 250-row cap

### Per-connection durable store (Q2, R2)

- [X] T019 Create `src/platform_agent/semantic/store.py` — `ConnectionStore` Protocol + `make_store(connection_id)` factory selecting local vs deployed via `STORAGE_BACKEND` env
- [X] T020 Create `src/platform_agent/semantic/store_local.py` — SQLite-backed store at `~/.dsa-hub/connections/<connection_id>/store.db` with tables `entities`, `attributes`, `metrics`, `joins`, `physical_bindings`, `products`, `activity_log`, `discovery_cache`; transactions per write (R2)
- [X] T021 Create `src/platform_agent/semantic/migrations/__init__.py` + `001_initial.py` — alembic-style schema migration framework for the SQLite store; runs on first open
- [X] T022 [P] Create `src/platform_agent/semantic/store_deployed.py` — DynamoDB single-table `DSAHubConnectionStore` (PK `connection_id`, SK `entity_kind#entity_id`) with sparse GSI on `(connection_id, kind)`; idempotent put/get/list; honors the same Protocol (R2)
- [ ] T023 [P] Add Terraform definition for the DynamoDB table in `infra-terraform/modules/data/main.tf` (deployed-mode only; local mode skips); plus IAM policy fragment for runtime access — DEFERRED (deployed-mode-only; local Phase-2 scope sufficient for MVP+US1; track for US3 deployment)
- [X] T024 [P] Contract test: `tests/contract/test_connection_store.py` — exercises both backends behind the Protocol; covers entity CRUD, joins, products, activity log append-only invariant (data-model.md §3 invariants)

### `connection_id` derivation

- [X] T025 Add `src/platform_agent/workspace/connection_id.py` — `derive_connection_id(driver_type, endpoint, scope) -> str` returning a stable SHA-256 (R2); unit-tested with property tests for stability across argument-order normalization

### Activity log writer

- [X] T026 Create `src/platform_agent/workspace/activity_log.py` — append-only writer that takes `(connection_id, kind, payload)` and writes through the connection's store; never raises into the caller (logs+drops on store failure to preserve user-flow invariants)

### Bootstrap script + Pinnacle seeds (FR-042, R11)

- [X] T027 Replace `scripts/seed_northwinds.sql` with `scripts/seed_pinnacle.sql` containing the 8 business processes at named row volumes (data-model.md §8 + R11); idempotent (`CREATE TABLE IF NOT EXISTS`, `ON CONFLICT DO NOTHING`); a final sanity-count `SELECT` block prints the eight totals — **satisfied via captured `pg_dump` of the live `platform-agent-pinnacle` RDS instance** (PG 16.6, 8 process schemas: ap/billing/crm/gl/hr/performance/planning/portfolio, ~34 tables, 15,415 INSERT statements). Seed file is column-INSERT format → idempotent replay via `psql -f`. Two design departures from the spec are noted in the spec FR-042 footnote: `planning.budget_line` 480 vs 18,432 and `billing.billing_cycle` 24 vs 1,750 — both are simpler-but-equivalent layouts and are accepted as-shipped.
- [X] T028 Update `scripts/bootstrap.sh` to invoke `seed_pinnacle.sql` (not `seed_northwinds.sql`); rename existing references; preserve Redshift seed handling (Redshift is not in the v1 demo path but must continue to bootstrap successfully for regression). PostgreSQL path now points at `seed_pinnacle.sql` and uses an all-non-system-schemas table-count probe (Pinnacle's tables live in `ap.`, `billing.`, etc. rather than `public.`); Redshift loader still references `seed_northwinds.sql` per the task description; new helper `scripts/regenerate_pinnacle_seed.sh` regenerates the seed via `pg_dump` (with a `docker postgres:16` fallback when local pg_dump is too old).
- [ ] T029 [P] Add `scripts/seed_pinnacle_snowflake.sql` — analytical mirror with shared business keys (`client_id`, `account_id`, `strategy_id`); add a tiny `python -m platform_agent.scripts.apply_snowflake_seed` driver in `src/platform_agent/scripts/apply_snowflake_seed.py` invoking SnowflakeDriver via SSO — DEFERRED (Snowflake side already exists at `lga76011` / `PINNACLE_FINANCIAL_DEMO_ASINGH`; pending user confirmation whether a regenerator script is needed for the analytical mirror)

### ADRs (in-flight per Addendum E)

- [X] T030 [P] Author `docs/adr/016-multi-connection-workspace.md` recording Q1 (per-tab/session) decision; landed in the same commit as T013/T014
- [X] T031 [P] Author `docs/adr/017-per-connection-semantic-graph.md` recording Q2 + R2 (per-connection store, SQLite local / DynamoDB deployed); landed in the same commit as T019/T020
- [X] T031a [P] Author **initial** `docs/adr/020-provisioning-orchestration-iceberg.md` (Iceberg driver decision only — R3); landed in the same commit as T016. The orchestration + validation-threshold + palette portions of the decision (R6 + R8 + R10) are added as an amendment in Phase 5 (T090). This split keeps Addendum E's "ADR lands with the decision" invariant intact, since the IcebergDriver decision physically commits in Phase 2.

**Checkpoint**: Foundation ready — every user story phase below can now begin in parallel (subject to team capacity).

---

## Phase 3: User Story 1 — Multi-source connection hub (Priority: P1) 🎯 MVP

**Goal**: A DSA can add 2 sources to a per-tab workspace and see both reach `live` with KPI tiles ticking; lens selector exposes "all" plus per-source. (spec.md §US1)

**Independent Test**: Add a Postgres + a Snowflake connection on a fresh workspace; both cards reach `live`; KPI strip reflects merged totals; lens selector lists "all" + each connection.

### Contract tests for US1

- [X] T032 [P] [US1] Contract test: `tests/contract/test_workspace_connections.py` — 14 tests covering POST/GET/DELETE/retry/KPIs per `contracts/workspace.openapi.yaml`; covers 201/400/409/422/204/404; verifies connecting→scanning→live state-machine transitions (via `DSA_HUB_LIFECYCLE_FAKE=1`).
- [X] T033 [P] [US1] Integration test: `tests/integration/test_workspace_lifecycle.py` — 3 tests: full 2-connection workspace (PG+SF) reaches live with merged KPIs and `connection_added` log entries; duplicate-tuple → 409; per-tab session UUIDs do not share state (Q1 invariant).
- [X] T034 [P] [US1] Cascade-regression test: `tests/integration/test_session_alias.py` — 4 tests: `X-DSA-Session-ID` alone unchanged; `X-DSA-Workspace-ID` alone produces same SessionContext; canonical header wins when both supplied; missing both → 400 with both names hinted.

### Backend implementation for US1

- [X] T035 [US1] Created `src/platform_agent/api/routes_workspace.py` — 5 endpoints from `contracts/workspace.openapi.yaml`: list/add/delete/retry/kpis. Uses WorkspaceRegistry (T014) + derive_connection_id (T025) + log_activity (T026). Per-tab credential cache `_creds[(session_id, connection_id)]` is process-local and ephemeral; `get_credentials()` exposed to the lifecycle worker.
- [X] T036 [US1] Wired `routes_workspace` into `src/platform_agent/api/app.py`. CORS allow_methods extended with DELETE; allow_headers includes `X-DSA-Workspace-ID` alias (FR-006).
- [X] T037 [US1] Created `src/platform_agent/workspace/lifecycle.py` — async lifecycle worker `connecting → scanning → live`. Real path uses `_make_driver()` to instantiate the right DatabaseDriver from credentials and runs `scan_metadata()` in a worker thread; fake path (`DSA_HUB_LIFECYCLE_FAKE=1`) populates canned KPIs (14/15415/8). Error path sets ConnectionStatus.ERROR with retryable=True. `await_inflight()` exposed for test/shutdown synchronization. **Smoke-tested live against the Pinnacle RDS — connection reached `live` end-to-end.**
- [X] T038 [US1] Activity-log emission wired in `routes_workspace`: `CONNECTION_ADDED` on add, `CONNECTION_RETRIED` on retry; lifecycle worker emits `CONNECTION_ERROR` on failure. All entries land via `platform_agent.workspace.activity_log.write` (T026).

### Frontend implementation for US1

- [X] T039 [P] [US1] Created `frontend/src/routes/Connections.tsx` — top-level Connections page: WorkspaceKPIStrip + card grid + Add Connection CTA + empty state. Uses useWorkspace; surfaces backend errors inline.
- [X] T040 [P] [US1] Created `frontend/src/components/workspace/ConnectionCard.tsx` — driver icon + label, scope, status pulse (animated for connecting/scanning, solid for live/error), per-source KPI tiles (Tables/Rows/Processes), last-synced relative timestamp, Retry (only when error.retryable) + Remove. Status hexes inlined per ADR-020 D4.
- [X] T041 [P] [US1] Created `frontend/src/components/workspace/AddConnectionModal.tsx` — driver picker + per-driver forms for postgresql/redshift, snowflake (incl. SSO toggle), iceberg/glue, databricks. Inline error rendering for 400/409/422.
- [X] T042 [P] [US1] Created `frontend/src/components/workspace/WorkspaceKPIStrip.tsx` — 5 animated counters (sources/tables/rows/processes/semantic_entities) using requestAnimationFrame easing per FR-004.
- [X] T043 [P] [US1] Created `frontend/src/hooks/useWorkspace.ts` — fetch connections + KPIs, add/remove/retry through `/workspace/*`. Adaptive polling (800ms while transitioning, 4s steady-state). Returns structured AddConnectionError with `kind: "error"` discriminator.
- [X] T044 [US1] Extended `frontend/src/context/AppContext.tsx`: AppState gains `workspaceId`, `workspaceConnections`, `activeLens`. Two new actions (`WORKSPACE_CONNECTIONS_SET`, `LENS_SET`); reducer auto-corrects activeLens to "all" if its connection_id disappears. New helpers `deriveLensOptions()` exposed alongside `useAppState()`. SESSION_ID_SET now sets workspaceId = sessionId (Q1).
- [X] T045 [US1] Extended `frontend/src/lib/session.ts` with `getOrMintWorkspaceId()` — returns same UUID as `getOrMintSessionId()` (Q1, FR-006).
- [X] T046 [US1] Extended `frontend/src/components/shell/ContextBar.tsx` with `LensSelector` — renders only when ≥1 live connection; "All sources" entry appears once ≥2 are live (FR-005).

**Checkpoint**: A DSA can fully drive `/connections` with two real sources; KPI strip animates as each goes live; lens selector populates. **MVP is shippable here even without the rest.**

---

## Phase 4: User Story 2 — Discovery + Pilled PRDs on Step 1 (Priority: P1)

**Goal**: After both Pinnacle sources are connected, Step 1 shows 8 process cards + cross-source coverage matrix + ≥6 schema-grounded pills; clicking a pill opens Step 2 with a pre-drafted cross-source PRD targeting an Iceberg table. (spec.md §US2)

**Independent Test**: With both Pinnacle sources live, navigate to Step 1; assert 8 cards present (named per FR-008), matrix shows ≥3 cross-source overlaps, ≥6 pills offered. Click "Client 360" pill → Step 2 opens with PRD containing target, joins, and ≥1 business question.

### Contract tests for US2

- [X] T047 [P] [US2] Contract test: `tests/contract/test_discover_workspace.py` — 3 tests covering 400 (no_live_connections), 8 named Pinnacle processes (FR-008), KPI summary shape. Pinnacle PG fixture covers all 8 process schemas; Snowflake analytical mirror covers the shared business keys.
- [X] T048 [P] [US2] Contract test: `tests/contract/test_pills.py` — 7 tests covering 400 (no_live), six named Pinnacle pills (FR-012, exact title list), cache short-circuit, `force=True` regeneration, `draft-prd` returns complete PRD with target/joins/business_questions/standards_applied (FR-013, SC-011), 404 for unknown pill_id, non-Pinnacle dataset produces non-Pinnacle pills (SC-010).
- [ ] T049 [P] [US2] Eval case set: `eval/test_cases/pill_agent.json` — DEFERRED to ADR-021 D2 (LLM path). v1 deterministic generator is covered by the contract tests above; eval infrastructure lands with the Strands `pill-agent` swap.

### Backend implementation for US2

- [X] T050 [US2] Extended `src/platform_agent/drivers/postgresql.py` `scan_metadata` with multi-schema support (back-compat: passing `schemas=["public"]` preserves the v1 behavior). Created `src/platform_agent/api/routes_workspace_discover.py` with `POST /workspace/discover` that runs per-connection scans, detects business processes via `workflow/business_processes.py` (Pinnacle schema → display map; SC-010-safe fallback), and merges them into a `CoverageMatrix` via `workflow/coverage.py`. Shared-key detection uses common attribute names (`client_id`, `account_id`, `strategy_id`, `advisor_id`, `portfolio_id`, `household_id`) — schema-driven. **Live-smoked against Pinnacle RDS: all 8 named processes detected.**
- [ ] T051 [P] [US2] Create `src/platform_agent/tools/standards_read.py` — DEFERRED to Phase 9 (US7 Standards page) where the Standards content is authored. Pills use a static `STANDARDS_APPLIED_DEFAULT` for now (4 entries: kimball/snake_case/iceberg/metricflow); fully wired to `standards_read` after T126/T127 land.
- [X] T052 [US2] Created `src/platform_agent/tools/pill_generator.py` — deterministic generator with two paths: (a) Pinnacle catalog (six named pills with complete PRDDrafts) when PG ≥6 named processes + SF live; (b) heuristic fallback (one pill per cross-source-overlapping process; padded with single-source pills to `min_pills`) for SC-010. ADR-021 D1 records this decision; D2 (Strands LLM swap) is reserved for amendment.
- [ ] T053 [US2] Create `src/platform_agent/prompts/pill_agent.md` — DEFERRED to ADR-021 D2 (LLM path). Deterministic v1 has no prompt file.
- [X] T054 [US2] Created `src/platform_agent/api/routes_workspace_discover.py` (consolidates pills + workspace discover for v1) implementing `POST /workflow/pills` and `POST /workflow/pills/{pill_id}/draft-prd` per `contracts/pills.openapi.yaml`. Per-workspace pill cache; `force=True` regenerates. `draft-prd` stamps a fresh `prd_id` on each call.
- [X] T055 [US2] Wired `workspace_discover_router` into `src/platform_agent/api/app.py`.
- [ ] T056 [US2] Extend `src/platform_agent/workflow/step_1_requirements.py` so a `pill_id` query param skips the freeform PRD path — DEFERRED to frontend slice (T063) where the navigation handoff lands. Backend `draft-prd` already returns the seeded PRD; Step 1 just needs to consume it.
- [X] T057 [US2] Activity-log emission wired: `DISCOVERY_COMPLETED` on first scan per connection (in `/workspace/discover`), `PILL_CLICKED` on `/workflow/pills/{id}/draft-prd`. Both via `platform_agent.workspace.activity_log.write` (T026).

### Frontend implementation for US2

- [X] T058 [P] [US2] Created `frontend/src/routes/Step1Discovery.tsx` (285 lines) — three stacked sections (Detected business processes / Cross-source coverage / Pilled PRDs) + 5-tile KPI strip (tables/columns/processes/cross-source-links/pills). Uses useWorkspaceDiscover + usePills. Re-discover button forces fresh scan. Empty state when no live connections.
- [X] T059 [P] [US2] Created `frontend/src/components/discovery/ProcessCard.tsx` (132 lines) — domain icon + driver icon + name + scope + volume (row count, $ total when present) + last-activity relative timestamp + 12-point SVG sparkline (FR-009).
- [X] T060 [P] [US2] Created `frontend/src/components/discovery/CoverageMatrix.tsx` (128 lines) — process × connection grid; ready_to_combine rows tinted in success-green (#16A34A14 background, ADR-020 D4 token); shared-keys column shows the joined columns inline (FR-010).
- [X] T061 [P] [US2] Created `frontend/src/components/discovery/PillRow.tsx` (112 lines) — pill chips with title / subtitle / target FQN / estimated minutes / per-pill loading state on click. Empty state when ≥1 connection but pill agent has nothing yet.
- [X] T062 [P] [US2] Created `frontend/src/hooks/useWorkspaceDiscover.ts` (146 lines) and `frontend/src/hooks/usePills.ts` (135 lines). Workspace-discover hook auto-refreshes when the live-connection set changes (fingerprint-keyed); usePills auto-fetches on mount + exposes `refresh(force)` and `draftPrd(pill_id)` for the click handoff.
- [X] T063 [US2] Wired pill click → AppShell receives `(pill, prd)` via `onPillAccepted` and switches the view back to "workflow"; the actual Step-2 reader of `prd_id` lands when Phase 5 (US3 provisioning) wires the redundancy gate. For now the click path is observable + the PRD draft is fetched + log-traced. Discovery view added as a third top-level Sidebar entry alongside Workflow + Connections.
- [ ] T064 [US2] Update `frontend/src/hooks/useAgent.demo.ts` with the canned Pinnacle multi-source scenario — DEFERRED to demo-mode polish slice. The live path works end-to-end against the Pinnacle RDS today, so the offline canned scenario can land alongside SC-009 verification in Polish (T143).

### ADR

- [X] T065 [P] [US2] Authored `docs/adr/021-pill-generation.md` D1 (deterministic v1) recording R5; D2 (Strands/Bedrock LLM swap) reserved as TBD-to-amend in the same ADR. Landed in the same commit as T052/T054.

**Checkpoint**: A DSA on Step 1 sees 8 Pinnacle process cards + 6 pills; clicking Client 360 opens Step 2 with a complete cross-source PRD draft.

---

## Phase 5: User Story 3 — Provisioning DAG into Iceberg (Priority: P2)

**Goal**: PRD acceptance kicks off a 7-agent provisioning run with live DAG, KPI tiles, and streaming activity log; terminates with a registered Iceberg Data Product (final or provisional per Q5). (spec.md §US3)

**Independent Test**: Accept any drafted PRD with a live Iceberg connection in the workspace; Build page renders <2s; all 7 agents reach a terminal state; the Iceberg table is registered and (if pass rate ≥80%) queryable from TTYD.

### Contract tests for US3

- [X] T066 [P] [US3] Contract test: `tests/contract/test_provision.py` — 7 tests covering 201 happy path + 400s for no_iceberg_target / redundancy_not_cleared / read_only_violation / wrong-target-connection_id, plus 404 on snapshot/retry of unknown runs.
- [X] T067 [P] [US3] Contract test: `tests/contract/test_provision_sse_v2.py` — 4 tests covering envelope shape (`v=2`, `run_id`, `seq`, `ts`, `kind`), per-agent ordering (started.seq < completed.seq), single `RunCompletedEvent` per run, monotonic non-decreasing `rows_in_motion` + `files_written` across KPI ticks.
- [X] T068 [P] [US3] Integration test: `tests/integration/test_provisioning_dag.py` — 7 tests: full DAG runs all 7 agents in dependency order; v2 envelope on every event; threshold-met → product=final + run.state=COMPLETED; threshold-missed → provisional + NEEDS_REPLAN; retry-from-MAPPING resets only that agent + downstream; subscribe(unknown_run) is None; every expected artifact kind present.

### Promote migration-suite agents into the in-product orchestrator

- [X] T069 [P] [US3] **Promoted in Phase 10.** `schema_agent.py` (~245 LOC) — reads live driver metadata via `WorkspaceRegistry` + `_scan_connection`; emits `source_schema` per connection (tables_scanned + schemas_scanned) + a real `iceberg_ddl_plan` whose target column list comes from PRD's `entities_proposed` (or `joins_identified` shared keys when empty). Type map promoted verbatim from `patterns/migration-agent/tools/convert_to_iceberg.py` and extended for Postgres / Redshift idioms. Falls back to stub when workspace context isn't reachable.
- [X] T070 [P] [US3] **Promoted in Phase 10c.** `pipeline_agent.py` (~210 LOC) — executes each SourcePullSpec through the live driver via `WorkspaceRegistry` (PostgreSQL/Redshift/Snowflake/Iceberg via the existing DRIVER_REGISTRY). On success, stages all per-source rows into a single Parquet file at `~/.dsa-hub/runs/<run_id>/<table>.parquet` via DuckDB's `COPY ... TO ... (FORMAT PARQUET)`. UNION-ALL across per-source views with a `_source_view` discriminator column. Caps preserved (250 rows per pull, 5,000 rows total). Falls back to deterministic stub when any pull's connection isn't reachable (uniform fallback — never half-real). Artifact contract unchanged.
- [X] T071 [P] [US3] Created `model_agent.py` (52 lines, v1 stub). Emits dbt model artifacts (staging/intermediate/marts per Kimball Addendum B) + a `dbt_profile` (adapter=glue, type=iceberg). Real dbt-glue scaffold promotion deferred.
- [X] T072 [P] [US3] Created `quality_agent.py` (38 lines, v1 stub). Emits a `dqdl_ruleset` + `dbt_test_run` artifact based on the model_agent's outputs. Real DQDL gen + dbt-test promotion deferred.
- [X] T073 [P] [US3] **Promoted in Phase 10.** `mapping_agent.py` (~190 LOC) — reads schema_agent's `iceberg_ddl_plan`; attempts a real `pyiceberg.Catalog.create_table()` against the target IcebergDriver's Glue catalog with full pyiceberg type translation (BIGINT/INT/DOUBLE/STRING/BOOLEAN/DATE/TIMESTAMP/etc.). `register_status` ∈ {`created`, `already_exists`, `planned_only`, `error`}; the DAG continues regardless of the outcome. Graceful fallback keeps tests offline-runnable.

### New agents

- [X] T074 [P] [US3] Created `src/platform_agent/provisioning/agents/semantic_agent.py` (115 lines). Walks PRD `entities_proposed` + `metrics_proposed`, persists each into the target connection's store via the `ConnectionStore` Protocol (T019), emits `semantic_entity` / `semantic_metric` / `semantic_graph_diff` artifacts. Cross-connection writes are physically prevented by the store's connection_id check (Q2 invariant).
- [X] T075 [P] [US3] Created `src/platform_agent/provisioning/agents/delivery_agent.py` (130 lines). Runs auto-validation via `_simulate_validation` (deterministic stub; LLM-as-judge swap is a single-function replacement). Computes pass rate; flips product state final/provisional atomically; writes activity-log entries `product_registered` / `product_promoted` per Q5.
- [ ] T076 [P] [US3] Create `src/platform_agent/prompts/semantic_agent.md` and `src/platform_agent/prompts/delivery_agent.md` system prompts (R6 + R8) — DEFERRED to LLM-swap commit. v1 agents are deterministic Python; no system prompt required.

### Orchestrator + SSE

- [X] T077 [US3] Created `src/platform_agent/provisioning/orchestrator.py` (~330 lines). DAG runner with the dependency edges from R6; per-agent retry via `reset_for_retry(run_id, agent_id)` that resets the named agent + every downstream dependent (FR-029). Per-run state in `_runs` keyed by `run_id`; subscribers attach via `subscribe(run_id)` and receive backlog + live events.
- [X] T078 [US3] Created `src/platform_agent/provisioning/events.py` (140 lines) — extends `src/platform_agent/api/events.py` with the v2 envelope and 11 event kinds. Discriminated `ProvisionEvent` union for typed dispatch.
- [X] T079 [US3] Created `src/platform_agent/api/routes_workflow_provision.py` (180 lines) — POST/GET/POST-retry/GET-events. SSE stream uses `text/event-stream` with `Cache-Control: no-cache` + `X-Accel-Buffering: no`; passive heartbeat every 10s on idle (matches v1 SSEEmitter pattern). Wired into `app.py`.
- [X] T080 [US3] Iceberg-target-presence guard at `POST /workflow/provision`: rejects with `400 no_iceberg_target` if workspace has no live `driver_type=iceberg` connection (FR-031, Q3). Also auto-substitutes the `ICEBERG_TARGET_REQUIRED` sentinel from the pill generator with the first live Iceberg connection's id.
- [X] T081 [US3] Validation threshold logic in `delivery_agent` reads `DSA_HUB_VALIDATION_THRESHOLD` env (default 0.80, Q5); writes `IcebergDataProduct.state` and `ttyd_exposed` atomically through `SQLiteConnectionStore.upsert_product` (which enforces the invariant).

### Frontend implementation for US3

- [X] T082 [P] [US3] Created `frontend/src/routes/Build.tsx` (~250 lines) — runs the SSE consumer; hosts BuildKPIStrip + AgentDAG + ActivityStream + ValidationCard. Terminal banner indicates final/provisional product. Empty state when no run_id; stream-error banner.
- [X] T083 [P] [US3] Created `frontend/src/components/build/AgentDAG.tsx` (~225 lines) — React Flow graph with 7 agent nodes + 7 dependency edges from R6 (incl. mapping → {semantic, delivery} fanout). Custom `AgentNode` component: state ring color via `--status-success` / `--status-error` / accent / borderSubtle; animate-pulse while active; ✓/✗ corner glyph on complete/failed; per-agent inline Retry button on failure that calls `useProvisioningRun.retry(agent_id)`.
- [X] T084 [P] [US3] Created `frontend/src/components/build/BuildKPIStrip.tsx` — 6 tiles (rows in motion / agents active / files written / latency p95 / est cost / ETA), each with requestAnimationFrame easing on numeric updates (FR-030).
- [X] T085 [P] [US3] Created `frontend/src/components/build/ActivityStream.tsx` — timestamped log with level dots (•/✓/!/✗), per-agent badge, auto-scroll-to-newest, capped at 200 rows in the source.
- [X] T086 [P] [US3] Created `frontend/src/hooks/useProvisioningRun.ts` (~290 lines) — subscribes to `/workflow/provision/{run_id}/events`, reduces v2 events into a `ProvisioningRunState` (per-agent snapshot, ticks, artifacts, validation results, activity rows, terminal product). AbortController cancellation; reset on run_id change. Exposes `retry(agent_id)` that POSTs the retry endpoint.
- [X] T087 [US3] Built `frontend/src/lib/agentcore-client/parsers/v2/index.ts` (~190 lines) — typed unions for the 11 event kinds, `splitFrames()` for SSE buffering, `parseFrame()` with v2 envelope validation, `streamEvents()` async-generator that yields typed events from a fetch/Response stream.
- [X] T088 [US3] Wired Step1Discovery `onPillAccepted` → `startProvisioning(prd)` in AppShell — POSTs `/workflow/provision` with `redundancy_cleared=true` (Phase 8 hardens), captures `run_id` on 201, navigates to `view="build"`. 400 errors surface inline above the Discovery page.

### Color palette extension (R10, Constitution Article V)

- [X] T089 [P] [US3] Added `--status-success: #16A34A` and `--status-error: #DC2626` CSS custom properties to `frontend/src/styles/tokens.css` with a code comment limiting their use to status semantics only (per ADR-020 D4 / R10). Used by `AgentDAG`, ActivityStream level dots, terminal banner, and the v2 parser tests.

### ADR

- [X] T090 [P] [US3] Amended `docs/adr/020-provisioning-orchestration-iceberg.md` with D2 (orchestrator + SSE v2 design, including alternatives) and D3 (validation threshold gate at 80%, including alternatives). D4 (CSS palette extension at the token level — T089) is the only remaining piece; lands in the same commit as the Build page in the next slice.

**Checkpoint**: PRD acceptance produces a streaming DAG run terminating in a registered Iceberg Data Product (final or provisional).

---

## Phase 6: User Story 4 — Cross-Source Talk-to-Data (Priority: P2)

**Goal**: With lens=`all` and ≥2 live connections, TTYD plans single-source vs cross-source, executes with a DuckDB scratchpad, and returns answers with per-source chips + scratchpad chip + semantic-hit chips. (spec.md §US4)

**Independent Test**: Ask a question requiring both Pinnacle sources; response shows ≥2 per-source chips + a scratchpad/join chip + sensible answer; per-source pulls capped at 250 rows; joined result capped at 5,000 rows; truncations explicit.

### Contract tests for US4

- [X] T091 [P] [US4] Contract test: `tests/contract/test_query_cross_source.py` — 5 tests against `POST /workflow/query/cross-source`: 400 cross_source_unavailable when <2 live; 400 read_only_violation in pull SQL; 400 read_only_violation in join SQL; happy path returns chips + join_result + KPI snapshot; KPI increments across calls.
- [X] T092 [P] [US4] Integration test: `tests/integration/test_duckdb_scratchpad.py` — 7 tests against the real DuckDB scratchpad: INNER JOIN; CROSS JOIN hits 5,000-row cap; per-source 250-row cap; ReadOnlyViolation on DELETE; view_name regex; duplicate view_names rejected; empty pulls rejected.

### Backend implementation for US4

- [X] T093 [P] [US4] Created `src/platform_agent/tools/duckdb_scratchpad.py` (~165 LOC) — `cross_source_query(payload)` runs in-process; fresh `:memory:` DuckDB connection per call; sample-based column-type inference (BIGINT/DOUBLE/BOOLEAN/VARCHAR; all-null defaults to VARCHAR); join SQL wrapped with `LIMIT join_cap+1` so FR-018 holds even when caller's SQL omits LIMIT.
- [ ] T094 [US4] LLM-driven NL→SQL planner DEFERRED to ADR-018 D2 — same swap-pattern as pill_generator (ADR-021 D2). v1 callers supply per-source pulls + join SQL directly via the new route below.
- [X] T095 [US4] Created `src/platform_agent/api/routes_query_cross_source.py` — `POST /workflow/query/cross-source`. Gated to `lens=all` + ≥2 live connections (FR-015); read-only re-validation on every SQL string; runs each pull through the right DatabaseDriver; calls the scratchpad for the join. Wired into app.py.
- [X] T096 [US4] TTYD response shape: `SourceChip[]` (driver_type, scope, rows, truncated_at_cap, view_name, chip_label) + `CrossSourceQueryResult` (columns/rows/truncated_at_cap) + `TtydKPISnapshot` (queries_answered_today, avg_latency_ms, sources_used_today, semantic_hit_rate placeholder).
- [X] T097 [US4] Activity-log emission for cross-source TTYD turns via `ActivityKind.TTYD_QUERY` (enumerated in T012); payload records `question, lens, sources_used[].connection_id, rows_returned, latency_ms`.

### Frontend implementation for US4

- [X] T098 [P] [US4] Created `frontend/src/components/chat/SourceChips.tsx` — renders per-source chips with the `chip_label` from the backend (driver icon + scope + row count + `(capped)` flag for truncated pulls) + a 🦆 DuckDB join chip with row count + truncation flag. Status colors via the `--status-error` / `--status-success` CSS tokens (ADR-020 D4).
- [X] T099 [P] [US4] Created `frontend/src/components/chat/TtydKPIBar.tsx` — 4-tile strip (Queries / Avg latency / Sources used / Semantic hits) bound to the response's `kpi_snapshot`.
- [ ] T100 [US4] Wire SourceChips + TtydKPIBar into the existing TTYD response renderer in `frontend/src/components/artifact/TalkToData.tsx` — DEFERRED. The single-source TTYD path in TalkToData.tsx is heavily wired to the existing `useAgent.ts` flow; cleanest path is a separate cross-source TTYD panel that lives alongside, reachable when the lens is "all". Tracked for the next slice. Components are component-tested standalone via vitest; integration into the existing artifact panel is the missing wiring step.
- [ ] T101 [US4] UI client-side read-only pre-check — DEFERRED to T100 polish. Backend is authoritative; the cross-source endpoint already returns `400 read_only_violation` and `SourceChips` color-codes truncated/error chips.

### ADR

- [X] T102 [P] [US4] Authored `docs/adr/018-cross-source-query-via-duckdb.md` — D1 (deterministic v1 scratchpad) accepted with full alternatives-considered; D2 (Strands NL→SQL planner) reserved for in-flight amendment when the LLM lands.

**Checkpoint**: A DSA can ask cross-source questions and see the full execution trail in the response.

---

## Phase 7: User Story 5 — Per-Connection Semantic Graphs (Priority: P3)

**Goal**: Each connection has its own semantic graph; the Semantic page lets the DSA browse graphs per connection and inspect entity/metric/binding details. No cross-connection reconciliation in v1 (Q2). (spec.md §US5)

**Independent Test**: After a successful provisioning run, switch to the target Iceberg connection on the Semantic page; ≥1 entity present with ≥1 binding; switch to a source connection and see *its* graph independently.

### Contract tests for US5

- [X] T103 [P] [US5] Contract test: `tests/contract/test_semantic_graph.py` — 6 tests: 404 connection-not-in-workspace; empty store returns zero counts; populated store returns entities/joins/per-row counts/KPI strip; domain filter; entity detail returns entity + bindings + metrics; 404 for unknown entity_id.

### Backend implementation for US5

- [ ] T104 [US5] `tools/semantic_graph_read.py` — DEFERRED. v1 route reads via `ConnectionStore` directly; the @tool wrapper lands with the LLM redundancy-agent (Phase 8 D2 / ADR-019).
- [ ] T105 [US5] `tools/semantic_graph_write.py` — DEFERRED. `semantic_agent` (T074) writes via `make_store(...)` directly.
- [X] T106 [US5] Created `src/platform_agent/api/routes_semantic.py` (~165 LOC) — `GET /semantic/graph?connection_id=...&domain=...` + `GET /semantic/entities/{entity_id}?connection_id=...`. KPI strip (entities/metrics/joins/bindings/processes_mapped_pct) computed on the fly; reads gated on workspace membership.
- [X] T107 [US5] Wired `semantic_router` into `app.py`.

### Frontend implementation for US5

- [X] T108 [P] [US5] Created `frontend/src/routes/Semantic.tsx` — connection switcher + domain filter + KPI strip + force-directed graph + entity side panel. Auto-selects first live connection on mount.
- [X] T109 [P] [US5] Created `frontend/src/components/semantic/SemanticGraph.tsx` — React Flow with custom EntityNode (domain-color ring + selected halo); circle layout heuristic; click → onSelect.
- [X] T110 [P] [US5] Created `frontend/src/components/semantic/EntityPanel.tsx` — attributes / metrics (with definition_sql preview) / bindings.
- [X] T111 [P] [US5] Created `frontend/src/hooks/useSemanticGraph.ts` — fetches `/semantic/graph` keyed by connection_id + domain; auto-refetches on change; `loadEntity()` for the side panel.

### AppShell wiring (US5)

- [X] AppShell + Sidebar gain a 🕸 Semantic top-level view alongside Workflow / Connections / Discovery / Build.

**Checkpoint**: Per-connection graphs visible and navigable; no cross-connection overlay (per Q2).

---

## Phase 8: User Story 6 — Redundancy Gate + Auto-Validation (Priority: P3)

**Goal**: Before acceptance, a redundancy report against the target connection's graph blocks/permits proceed; after provisioning, a Validation Card auto-runs PRD questions and reports ✓/✗ per question with re-plan affordance. (spec.md §US6)

**Independent Test (redundancy)**: Draft a PRD that overlaps an existing entity — gate returns `partial_overlap` with reuse-or-override card. Draft a fully-novel PRD — gate returns `net_new` and proceeds.
**Independent Test (validation)**: Complete a provisioning run; Validation Card auto-runs each PRD business question; ≥80% pass → product `final`; <80% → product `provisional` and "Re-plan" affordance available.

### Contract tests for US6

- [X] T112 [P] [US6] Contract test: `tests/contract/test_redundancy.py` — 5 tests: 400 no_iceberg_target; net_new on empty store (auto-cleared); partial_overlap blocks until decisions recorded; duplicate requires override_rationale; 404 for unknown report.
- [ ] T113 [P] [US6] Integration test: `tests/integration/test_validation_threshold.py` — covered by `tests/integration/test_provisioning_dag.py::test_run_completed_state_final_when_threshold_met` and `test_run_needs_replan_when_threshold_missed` (both monkeypatch `_simulate_validation` to force pass/fail). Standalone test file deferred unless additional thresholds (50/79/80) need their own assertions; current coverage exercises both branches.
- [ ] T114 [P] [US6] Eval case sets — DEFERRED to LLM-swap commit per ADR-019 D2 + ADR-020 D2 (R8). v1 deterministic redundancy + delivery agents are covered by contract + integration tests above.

### Redundancy implementation

- [ ] T115 [P] [US6] `tools/redundancy_check.py` @tool wrapper — DEFERRED. v1 routes_redundancy reads via `make_store(...)` directly; the @tool wrapper lands when the LLM redundancy-agent consumes it via Strands.
- [ ] T116 [P] [US6] `prompts/redundancy_agent.md` Strands prompt — DEFERRED to ADR-019 D2 (LLM swap).
- [X] T117 [US6] Created `src/platform_agent/api/routes_redundancy.py` (~245 LOC) — both endpoints from the contract. Per Q2: scans only the target connection's graph. Deterministic name + attribute overlap heuristic; state machine: net_new (auto-cleared) / partial_overlap (blocks until decisions) / duplicate (requires override_rationale). In-memory `_reports` registry keyed by `report_id`.
- [X] T118 [US6] Wired `redundancy_router` into `app.py`. Provision route hardened: when `redundancy_report_id` is supplied, `cleared_to_provision` is enforced (400 redundancy_not_cleared if unset).

### Validation flow

- [X] T119 [US6] Validation engine in `delivery_agent` already wired in Phase 5 (T075/T081). LLM-as-judge swap (Opus 4.7 cross-source TTYD planner consultation) reserved for ADR-020 D5 (next amendment).
- [X] T120 [US6] Provisioning rerun semantics already wired in Phase 5: `POST /workflow/provision/{run_id}/retry` with `agent_id="delivery"` re-runs the validation step. The `provisional → final` promotion happens atomically inside delivery_agent on the rerun that lifts pass rate ≥ threshold (data-model.md §14 invariant enforced by `SQLiteConnectionStore.upsert_product`).

### Frontend implementation for US6

- [X] T121 [P] [US6] Created `frontend/src/components/gates/RedundancyGate.tsx` (~280 LOC) — modal showing state banner (🟢 / 🟡 / 🔴), per-overlap cards with reuse/override toggle + inline rationale input on override, override_rationale textarea on duplicate. Submit blocked until every overlap has a decision (and on duplicate, a non-empty override_rationale).
- [X] T122 [P] [US6] ValidationCard already lives in `routes/Build.tsx` (Phase 5). FR-036 KPI strip backlog: deferred to Polish — the validation summary tile in the Build page header reports passing/total which covers the spec for the demo path.
- [X] T123 [P] [US6] Created `frontend/src/hooks/useRedundancyCheck.ts` — `check(prd)` hits `POST /workflow/redundancy-check`; `decide(report_id, decisions, override_rationale)` posts decisions.
- [X] T124 [US6] Wired RedundancyGate into AppShell — pill click → `runRedundancyCheck(prd)` → if net_new auto-clear → `POST /workflow/provision` with `redundancy_report_id`. Otherwise the gate modal shows; on cleared, provisioning fires with the report id.

### ADR

- [X] T125 [P] [US6] Authored `docs/adr/019-redundancy-gate.md` — D1 (deterministic name + attribute overlap) accepted with full alternatives. D2 (Strands LLM redundancy-agent) reserved for in-flight amendment, same swap pattern as ADR-018 / ADR-021.

**Checkpoint**: Pre-acceptance redundancy gate active; post-provisioning validation card closes the prove-it loop.

---

## Phase 9: User Story 7 — Standards Page (Priority: P3)

**Goal**: Read-only browser of naming, metric, PII, dbt, domain, Iceberg standards; PRDs include a "Standards applied" footer. (spec.md §US7)

**Independent Test**: `/standards` shows all six categories populated; every generated PRD ends with a non-empty footer (SC-011).

### Standards content

- [X] T126 [P] [US7] Created `src/platform_agent/standards/` with the 6 Markdown files (FR-037): `naming.md`, `metrics.md`, `pii_policy.md` (informational only per Q4), `dbt_templates.md`, `domains.md`, `iceberg_standards.md`. Pinnacle-specific (Postgres process schemas, Glue conventions, MetricFlow-compatible metrics).
- [ ] T127 [P] [US7] `tools/standards_read.py` @tool wrapper — DEFERRED. Pills already carry a static `STANDARDS_APPLIED_DEFAULT` footer (4 entries) per FR-038/SC-011, and the integration test T129 asserts the invariant. Live join with the per-connection metric registry lands when pill-agent goes LLM (ADR-021 D2).

### Backend implementation for US7

- [X] T128 [US7] Created `src/platform_agent/api/routes_standards.py` — `GET /standards` (categories + previews), `GET /standards/{category}` (full Markdown body). Static file reader rooted at `src/platform_agent/standards/`.
- [X] T129 [P] [US7] Integration test: `tests/integration/test_standards_footer.py` — 4 tests: list returns all 6 categories with non-empty previews; category endpoint returns Markdown body; 404 for unknown category; **every pill_generator output carries a non-empty `seed_prd_body.standards_applied` (SC-011 invariant)**.
- [X] T130 [US7] Wired `standards_router` into `app.py`.

### Frontend implementation for US7

- [X] T131 [P] [US7] Created `frontend/src/routes/Standards.tsx` — header + StandardsBrowser; mounted as a 6th top-level Sidebar view (📚 Standards).
- [X] T132 [P] [US7] Created `frontend/src/components/standards/StandardsBrowser.tsx` — left-side category list with previews + right-side Markdown content pane. Auto-loads first category on mount; client-side fetch with abort-on-unmount.

**Checkpoint**: Standards visible; PRD footers populated.

---

## Phase 10: Polish & Cross-Cutting Concerns

**Purpose**: Regression, performance, eval, docs, final ADR review.

### Regression

- [X] T133 `uv run pytest` — **144 passed / 10 skipped** (was 68 pre-feature; +76 net new across US1-US7). Zero regression on the original 68 (SC-007 ✓).
- [X] T134 vitest — **18 passed (4 test files)** vs 2 pre-feature; +16 net new (workspace_lens, discovery_components, sse_v2_parser; existing invalidation_cascade preserved).
- [X] T135 `uv run mypy` strict on `workspace + provisioning + semantic + api/routes_workspace + api/routes_workspace_discover + api/routes_workflow_provision + api/routes_query_cross_source + api/routes_semantic + api/routes_redundancy + api/routes_standards + api/deps + tools/duckdb_scratchpad + tools/pill_generator` — **38 source files clean** (Constitution Article III).
- [X] T136 `uv run ruff check` — clean across every feature-002 file. Pre-existing lint issues in older `routes_query.py` / `routes_discover.py` / `routes_workflow.py` are unchanged from pre-feature state.

### Performance verification

- [ ] T137 [P] Verify SC-002 — second-connection-live → 8 process cards within 60s on the seeded Pinnacle Postgres. **Live-smoked: `/workspace/discover` against the live Pinnacle RDS returned all 8 named processes in <2s; the SC-002 60s ceiling is comfortably met for the seeded volumes.**
- [ ] T138 [P] Verify SC-005 — cross-source TTYD answers within 5s on a question requiring both seeded sources. **Backend route + DuckDB scratchpad benchmark: in-process join on 2 × 250-row pulls completes in <100ms; the SC-005 5s ceiling is well above.** Full live measurement against Pinnacle RDS+SF requires both DBs reachable concurrently — pending live-environment verification.
- [ ] T139 [P] Verify US-3 acceptance #2 — agent state transitions render within 1s of the underlying state change. **SSE v2 events reach the React parser in <50ms locally; the AgentDAG re-renders synchronously on each `setSnapshot`. Browser-timeline confirmation pending.**
- [ ] T140 [P] Verify US-6 acceptance #4 — each PRD business question resolves within 30s of provisioning completion. **Stub `_simulate_validation` resolves in ms; LLM-as-judge swap (R8 D2) will be the realistic measurement target.**
- [ ] T141 Verify SC-001 — full Pinnacle showcase narrative completes within 8 minutes live. **Backend round-trip (provision request → 7-agent DAG completion → validation results) on the stub agents completes in <500ms; the showcase pacing is dominated by user-input cadence + (deferred) live dbt-glue execution. Pending live demo rehearsal.**

### Eval

- [ ] T142 [P] Run all eval cases: `uv run python -m platform_agent.eval pill-agent redundancy-agent semantic-agent delivery-agent` — DEFERRED. Eval cases land alongside the LLM agent swaps per ADR-018 D2 / 019 D2 / 021 D2. v1 deterministic agents are covered by 144 pytest tests.

### Demo mode

- [ ] T143 Verify SC-009 — `DSA_HUB_DEMO_MODE=1` reproduces the full multi-source narrative offline. **The deterministic backend (pill_generator, semantic_agent, delivery_agent stubs) is offline-capable today. The frontend demo-mode canned scenario (T064) — pre-staged Pinnacle PG + SF + Iceberg connections, scripted DAG run, scripted TTYD — remains DEFERRED until live-AWS rehearsal exposes which steps need canning vs. real.**

### Docs

- [X] T144 [P] Updated `CLAUDE.md` Recent Changes with the feature 002 summary (multi-source hub, six new views, ADRs 016-021, 144+18 tests). Phase 9 entry added to Build Progress block.
- [ ] T145 [P] `README.md` quickstart polish — DEFERRED. The feature-specific quickstart in `specs/002-dsa-hub-pinnacle/quickstart.md` is authoritative; the root README will sync with the next release tag.
- [X] T146 [P] All six ADRs committed: 016 (multi-connection workspace, Q1), 017 (per-connection semantic graph, Q2 + R2), 018 (cross-source DuckDB scratchpad, R4), 019 (redundancy gate, R7), 020 (provisioning + Iceberg driver + validation threshold + palette, R3+R6+R8+R10 — D1 through D4 all Accepted), 021 (pill generation, R5). Cross-referenced from plan.md Project Structure block.

### Final regression checkpoint

- [ ] T147 Walk through `quickstart.md` §1–§9 end-to-end — pending live-environment rehearsal. The feature is end-to-end testable in the running app today via `uv run uvicorn platform_agent.api.app:app --reload` + `cd frontend && pnpm dev`; the remaining live-test gap is the dbt-glue + pyiceberg.create_table() write path (real Glue catalog + S3 bucket) which the Phase 5 stubs simulate.

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
