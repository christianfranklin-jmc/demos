# Implementation Plan: DSA Hub — Pinnacle Cross-Source

**Branch**: `002-dsa-hub-pinnacle` | **Date**: 2026-04-26 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/002-dsa-hub-pinnacle/spec.md`

## Summary

Evolve the DSA Platform from a single-source workflow into a per-tab multi-source hub. A **Workspace** owns N **Connections** (PostgreSQL, Snowflake, Redshift, Databricks, Iceberg/Glue), each connection owns its own per-connection **Semantic Graph** and catalog (no cross-connection reconciliation in v1 — see Clarification Q2). Step 1 becomes a Discovery + Pilled-PRD page that detects business processes and offers six schema-grounded cross-source product suggestions; clicking a pill auto-drafts a PRD declaring an Iceberg target. PRD acceptance gates on a **redundancy check** against the target Iceberg connection's graph and on the workspace having a user-added Iceberg/Glue connection (Q3); on accept, a 7-agent provisioning DAG (schema → pipeline → model → quality → mapping/Iceberg → semantic → delivery) streams live to a Build page with KPI tiles and an animated agent graph. The run terminates by registering an **Iceberg Data Product** — final + TTYD-queryable if auto-validation passes the 80% threshold (Q5), otherwise provisional. **Cross-source TTYD** uses an in-process DuckDB scratchpad to combine bounded per-source pulls. Single-source remains a degenerate case; the existing 51 pytest + vitest cascade suite must continue to pass.

## Technical Context

**Language/Version**: Python 3.12+ (backend, agents, Lambda tools); TypeScript 5.6 + React 18 (frontend) per Constitution Article II. CLI text-mode equivalent for every UI surface (three-frontend rule from CLAUDE.md).

**Primary Dependencies**:
- Backend: FastAPI (existing), Strands Agents SDK, Pydantic v2, psycopg2 / redshift_connector / snowflake-connector-python (existing drivers), **duckdb (new — `uv add duckdb`)** for cross-source scratchpad, **pyiceberg** (new — `uv add pyiceberg`) + boto3 Glue client for the Iceberg/Glue driver, dbt-postgres / dbt-redshift / dbt-snowflake / dbt-glue (existing + new dbt-glue for the Iceberg target), MetricFlow (existing).
- LLM: Bedrock — Sonnet 4 default; Opus 4.7 escalation for redundancy reasoning, cross-source query planning, pill generation per the spec input (mapped via existing `models.py`).
- Frontend: React 18, Vite 6, Tailwind 4, shadcn/ui (existing), **React Flow** (already in stack per CLAUDE.md mention) for both the Build-page agent DAG and the Semantic-page graph, existing `agentcore-client/parsers/v1` SSE plumbing extended to v2 events for `/workflow/provision/{run_id}/events`.

**Storage**:
- **Workspace state** (per-tab): in-memory + browser `sessionStorage` (extends existing `frontend/src/lib/session.ts`). No server-side persistence (Q1).
- **Per-connection durable assets** (semantic graph, discovery cache, registered products index, activity log): local mode → SQLite at `~/.dsa-hub/connections/<connection-id>/` (one file per connection, keyed by stable `connection_id`); deployed mode → DynamoDB single-table with `connection_id` as partition key + `entity_kind#entity_id` as sort key (matches existing AgentCore Memory pattern). Per Q2 each connection's store is independent.
- **Iceberg Data Products**: AWS Glue Catalog + S3 Parquet, written via the user-added Iceberg connection (Q3). The `iceberg.<glue_db>.<table>` reference is the durable identity.
- **Credentials**: per-tab session-only (Q1) — passed at connection-add time, held in backend session memory keyed by the per-tab UUID, never persisted to disk or SSM in local mode; deployed mode references existing Secrets Manager entries by ARN (no new secret writes from the UI).

**Testing**:
- Existing: 51 pytest tests, vitest cascade-invalidation suite — both must continue to pass without modification beyond the documented `source_id → workspace_id` rename alias (FR-006).
- New: pytest contract tests for `/workspace/connection`, `/semantic/graph`, `/workflow/provision`, `/workflow/provision/{run_id}/events`, `/workflow/redundancy-check`, `/workflow/pills`. Vitest for new connection-page state machine + multi-source lens behavior. Eval cases for pill-agent, redundancy-agent, semantic-agent, delivery-agent (added under `eval/test_cases/`).

**Target Platform**: macOS dev (Docker Compose for backend + Streamlit + React); AWS deployed via existing Terraform 3-module hierarchy (`infra-terraform/`). Browser target: latest Chrome/Safari/Firefox.

**Project Type**: Web application (React frontend + FastAPI backend + Streamlit alternate frontend + CLI entry point — already established in CLAUDE.md).

**Performance Goals** (from spec SCs and acceptance scenarios):
- Discovery: 8 Pinnacle business processes visible within 60s of second connection going live (SC-002).
- Pill generation: 6+ pills offered on Step 1 page-ready (US-2 acceptance #1: cards within 10s).
- Cross-source TTYD: question requiring both sources answered within 5s at seeded volumes (SC-005).
- Validation: each PRD question resolves within 30s of provisioning completion (US-6 acceptance #4).
- Build page: agent state transitions render within 1s (US-3 acceptance #2).
- End-to-end demo: full SC-001 narrative in under 8 minutes live.

**Constraints**:
- Read-only enforcement at every query path (FR-018, SC-006). SELECT/WITH only; write-keyword regex block; 250-row per-source pull cap; 5,000-row joined-result cap.
- PRD acceptance gated on Iceberg connection presence (FR-031, Q3).
- 80% validation threshold for product registration as final (FR-031, Q5).
- Single-source workflow regression: zero new flakes attributable to multi-source rework (SC-007).
- ADRs in-flight per Constitution Addendum E for the six new decisions (016–021 placeholders).

**Scale/Scope**:
- 1 DSA per browser tab (Q1).
- Workspace: 2–5 connections in the demo case (Pinnacle Postgres + Snowflake + Iceberg/Glue + optional extras); design for up to ~10 without UI degradation.
- Pinnacle data: ~250 tables across two source connections; 8 named business processes; row volumes per FR-042 (336 invoices / $5.6M AP, 1,680 fee invoices / $10.7M, $295M annual budget, 420 trades / $19.4M notional, 6,300 daily AUM snapshots, etc.).
- Provisioning DAG: 7 agents (schema, pipeline, model, quality, mapping/Iceberg, semantic, delivery).
- Pills: 6 minimum for Pinnacle; schema-driven for any other dataset.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Constitution v2.2.0** — universal Articles I–X plus Project Addenda A–E. Each gate evaluated against the spec scope.

| # | Gate | Status | Notes |
|---|---|---|---|
| I | Python default for non-frontend | ✅ Pass | All new backend code in Python 3.12+ via `uv`. No new languages introduced. |
| II | React 18 + TS strict + Vite + Tailwind for UI | ✅ Pass | Extends existing `frontend/`; no Redux/Zustand introduced. New routes (`/connections`, `/semantic`, `/build`, `/standards`) layered into existing shell. |
| III | Type hints + Pydantic + ruff + mypy strict | ⚠ Partial | All NEW code MUST be fully annotated with Pydantic boundaries; mypy strict for new modules. Pre-existing strict gaps acknowledged in constitution Sync Impact Report and not in this feature's scope to fix. |
| IV | Anthropic SDK / Bedrock + Strands + AgentCore | ✅ Pass | Reuses existing `models.py` Bedrock config (Sonnet 4 default, Opus 4.7 escalation). System prompts in dedicated files under `src/platform_agent/prompts/`. New agents: pill, redundancy, semantic, delivery — each with own prompt file. |
| V | Dark-first + phData palette + enterprise-grade + backend-mode visible + layout stability + meaningful empty states | ⚠ **Violation** | The original feature input specified an extended accent palette (`#00d4a0` green / `#fbbf24` amber / `#4f8fff` blue / `#a855f7` purple / `#f472b6` pink) that overlaps but does not match the phData palette (Navy `#1B2A4A`, Blue `#2563EB`, Teal `#0D9488`, Orange `#F97316`). DAG status colors are load-bearing for Story 3 and Story 7 (validation card ✓/✗). **Resolution**: map status colors onto phData where possible (active → Teal, in-progress → Orange, info → Blue) and limit off-brand additions to two semantic-only roles (success-green, error-amber/red) following enterprise UI norms. See Complexity Tracking. |
| VI | Agent UX rules: one question at a time, artifact = source of truth, gates deliberate, step-scoped personas, no future-step speculation | ✅ Pass | TTYD remains Strands-driven; redundancy gate is a deliberate blocking modal (FR-026); each agent in the 7-agent DAG has its own step-scoped prompt; pill-agent is invoked once per discovery and never speculates beyond the discovered schema. |
| VII | Separation of concerns + no secrets in source + one tool per file + realistic mock data + error states handled | ✅ Pass | New agent tools each in their own file under `src/platform_agent/tools/`. Demo-mode (FR-041) uses Pinnacle-realistic mock data per Article VII. Iceberg/Glue and DuckDB credentials flow through `.env`. |
| VIII | Every demo has a scripted moment + loading/error states visible + PLAN.md + README.md | ⚠ **Violation** | Constitution suggests live demo under 3 minutes; SC-001 sets 8 minutes. **Justification**: SC-001 is a *multi-feature showcase* covering 7 user stories end-to-end (connect → discover → pill → redundancy → provision → validate → TTYD), not a single-feature demo. Each individual story is independently demonstrable in under 3 minutes (US-1 acceptance scenarios = ~60s; US-2 = ~90s; US-3 = ~3min for a full provisioning run). The 8-minute number reflects the full-narrative replay, which the constitution does not preclude. See Complexity Tracking. |
| IX | pytest only + type safety first | ✅ Pass | Existing pytest + vitest. No new test framework. |
| X | Build only what spec says + ADRs for non-covered decisions + when in doubt do less | ✅ Pass | Spec is post-clarify; six new ADRs (016–021 placeholders) tracked in-flight per Addendum E. No silent defaults. |
| A | Driver-abstracted data access | ✅ Pass | New `MultiSourceDriver` is a *registry* over existing `DatabaseDriver` implementations, not a bypass. New `IcebergDriver` follows the same protocol (connect / query / scan_metadata / dbt config) — `iceberg.<glue_db>.<table>` references just like other drivers. |
| B | Kimball methodology | ✅ Pass | dbt projects emitted by provisioning continue to follow `fct_` / `dim_` / surrogate keys / staging-marts layering. New Iceberg products follow the same convention (e.g., `iceberg.pinnacle_360.fct_client_360`). |
| C | Agent guardrails: read-only default + DDL approval + DROP/TRUNCATE/ALTER blocked + cite table.column | ✅ Pass | FR-018 / SC-006 codify the read-only floor. Provisioning is the only write path and runs only after explicit acceptance. Existing guardrails from `tools/toolkit_ddl.py` extend to the new MultiSourceDriver routing. |
| D | Infrastructure as Code | ✅ Pass | New AWS resources (Glue Catalog DB for Iceberg products in deployed mode, optional DynamoDB single-table for per-connection semantic graphs) go in `infra-terraform/modules/data/`. No console changes. |
| E | ADRs in-flight + OTel + AgentCore evaluators | ✅ Pass | ADRs 016–021 (placeholder numbering) authored at the moment each decision lands. New agents emit OTel spans into the existing CloudWatch Traces pipeline. New eval test cases under `eval/test_cases/` for pill-agent, redundancy-agent, semantic-agent, delivery-agent. |

**Gate result**: Two flagged violations (palette extension; demo length). Both justified in Complexity Tracking; neither blocks Phase 0 research. Re-check after Phase 1.

## Project Structure

### Documentation (this feature)

```text
specs/002-dsa-hub-pinnacle/
├── spec.md              # ✅ written + clarified (5 Q&As recorded)
├── plan.md              # ✅ this file
├── research.md          # Phase 0 output (this command)
├── data-model.md        # Phase 1 output (this command)
├── quickstart.md        # Phase 1 output (this command)
├── contracts/           # Phase 1 output (this command)
│   ├── workspace.openapi.yaml
│   ├── discover.openapi.yaml
│   ├── pills.openapi.yaml
│   ├── redundancy.openapi.yaml
│   ├── provision.openapi.yaml      # SSE event schema v2
│   ├── semantic.openapi.yaml
│   └── ttyd-cross-source.openapi.yaml
├── checklists/
│   └── requirements.md  # ✅ updated post-clarify
└── tasks.md             # /speckit.tasks output (next phase, NOT created here)
```

### Source Code (repository root — extends existing layout)

```text
src/platform_agent/
  api/
    app.py                            # existing FastAPI app (lifespan extended)
    events.py                         # existing v1 SSE schema → bumped to v2 for /workflow/provision
    deps.py                           # existing X-DSA-Session-ID → also accepts X-DSA-Workspace-ID alias (FR-006)
    sse.py                            # existing SSEEmitter reused
    routes_workflow.py                # existing — extended for /workflow/provision (POST + SSE)
    routes_workspace.py               # NEW — POST/DELETE/GET /workspace/connection(s)
    routes_pills.py                   # NEW — POST /workflow/pills
    routes_redundancy.py              # NEW — POST /workflow/redundancy-check
    routes_semantic.py                # NEW — GET /semantic/graph (per connection_id)
    routes_query.py                   # existing — extended for cross-source path when workspace has 2+ live
    routes_discover.py                # existing — extended to merge per-connection results at workspace level
  workflow/
    steps.py                          # existing StepId enum + STEP_REGISTRY
    step_1_requirements.py            # existing — extended to consult Standards (FR-038)
    step_2_conceptual.py              # existing — extended to accept pre-drafted PRD from a pill click
    step_3_logical.py                 # existing
    step_4_detailed.py                # existing — terminal "Accept & provision" CTA wires to provisioning
  provisioning/                       # NEW — 7-agent orchestrator
    orchestrator.py                   # DAG runner with per-agent retry semantics (FR-029)
    events.py                         # provisioning event schema (extends v2 SSE)
    agents/
      schema_agent.py                 # existing in patterns/migration-agent — promoted to src
      pipeline_agent.py               # existing — promoted
      model_agent.py                  # existing — promoted
      quality_agent.py                # existing — promoted
      mapping_agent.py                # existing — promoted (Iceberg/Glue registration)
      semantic_agent.py               # NEW — writes entities/metrics into target connection's graph
      delivery_agent.py               # NEW — exposes new product to TTYD; writes activity-log entry; runs auto-validation
  semantic/                           # NEW — per-connection semantic graph store
    models.py                         # Pydantic: SemanticEntity, PhysicalBinding, Metric, Join
    store_local.py                    # SQLite implementation (~/.dsa-hub/connections/<id>/semantic.db)
    store_deployed.py                 # DynamoDB single-table implementation
    store.py                          # Protocol + factory (selects local vs deployed via env)
  workspace/                          # NEW — per-tab workspace registry (in-memory)
    registry.py                       # WorkspaceRegistry keyed by per-tab UUID
    multi_source_driver.py            # registry over DatabaseDriver instances; routes by source.schema.table
    activity_log.py                   # writes to per-connection durable store
  drivers/
    base.py                           # existing DatabaseDriver protocol — unchanged
    iceberg.py                        # NEW — IcebergDriver (Glue Catalog + S3 + pyiceberg)
    postgresql.py / redshift.py / snowflake.py  # existing
  tools/
    cross_source_query.py             # NEW — @tool, available when workspace has 2+ live connections
    pill_generator.py                 # NEW — @tool used by pill-agent
    redundancy_check.py               # NEW — @tool used by redundancy-agent
    semantic_graph_write.py           # NEW — @tool used by semantic-agent
    semantic_graph_read.py            # NEW — @tool used by TTYD planner + redundancy-agent
    activity_log_write.py             # NEW — @tool used by delivery-agent + provisioning orchestrator
    duckdb_scratchpad.py              # NEW — @tool, in-process DuckDB join executor with row caps
    standards_read.py                 # NEW — @tool used by Step 1 PRD draft
    # existing tools preserved: toolkit_connect, toolkit_scan, toolkit_query, toolkit_ddl,
    # dbt_generate, semantic_layer
  prompts/
    pill_agent.md                     # NEW
    redundancy_agent.md               # NEW
    semantic_agent.md                 # NEW
    delivery_agent.md                 # NEW
    steps/                            # existing — step prompts unchanged

frontend/src/
  routes/
    Connections.tsx                   # NEW — /connections page (workspace + cards + KPI strip)
    Semantic.tsx                      # NEW — /semantic page (per-connection graph viewer)
    Build.tsx                         # NEW — /build page (DAG + KPI tiles + activity stream)
    Standards.tsx                     # NEW — /standards page (read-only browser)
    Step1Discovery.tsx                # NEW — replaces today's Step 1 (processes + coverage map + pills)
  context/
    AppContext.tsx                    # existing — extended with workspaceId + activeLens + connections[]
  hooks/
    useWorkspace.ts                   # NEW — workspace state + connection CRUD
    useProvisioningRun.ts             # NEW — SSE consumer for /workflow/provision/{run_id}/events
    useSemanticGraph.ts               # NEW — per-connection graph fetch + filter
    usePills.ts                       # NEW — pill list + click-to-PRD
    useRedundancyCheck.ts             # NEW
    useAgent.ts                       # existing — extended for cross-source dispatch
  lib/
    session.ts                        # existing — adds workspaceId alongside sessionId
    adapters.ts                       # existing — extended for new payloads
    duckdb-row-caps.ts                # NEW — UI-side display helpers for truncation chips
    agentcore-client/parsers/v2/      # NEW — extends v1 parser with provisioning event types
  components/
    workspace/ConnectionCard.tsx      # NEW — per-connection card with KPI tile + status pulse
    workspace/AddConnectionModal.tsx  # NEW — driver-specific forms (PG / SF / RS / DB / Iceberg)
    workspace/WorkspaceKPIStrip.tsx   # NEW — animated counters
    discovery/ProcessCard.tsx         # NEW — business-process card with sparkline
    discovery/CoverageMatrix.tsx      # NEW — cross-source coverage map
    discovery/PillRow.tsx             # NEW — pilled PRD chips
    build/AgentDAG.tsx                # NEW — React Flow DAG
    build/BuildKPIStrip.tsx           # NEW
    build/ActivityStream.tsx          # NEW
    build/ValidationCard.tsx          # NEW (also used post-validation flow)
    semantic/SemanticGraph.tsx        # NEW — React Flow force-directed view
    semantic/EntityPanel.tsx          # NEW
    standards/StandardsBrowser.tsx    # NEW
    chat/SourceChips.tsx              # NEW — per-source chips on TTYD responses
    gates/RedundancyGate.tsx          # NEW — modal between Step 1 and Step 2

patterns/                             # existing 5-agent migration suite — agents PROMOTED into src/platform_agent/provisioning/agents/ rather than left under patterns/, with patterns/ kept as legacy reference

infra-terraform/modules/data/         # existing — adds Glue Catalog DB for Iceberg products + optional DynamoDB single-table for deployed-mode semantic graph
gateway/tools/                        # existing Lambda-backed Gateway tools — no change in v1 (cross-source TTYD runs in-process via DuckDB, not in Gateway Lambda)
scripts/
  bootstrap.sh                        # existing — UPDATED to seed Pinnacle Postgres schema + row volumes per FR-042
  seed_pinnacle.sql                   # NEW — replaces seed_northwinds.sql (DDL + 8 business processes at named volumes)
  seed_pinnacle_snowflake.sql         # NEW — analytical mirror with shared business keys
docs/adr/
  016-multi-connection-workspace.md         # NEW (in-flight)
  017-per-connection-semantic-graph.md      # NEW (in-flight)
  018-cross-source-query-via-duckdb.md      # NEW (in-flight)
  019-redundancy-gate.md                    # NEW (in-flight)
  020-provisioning-orchestration-iceberg.md # NEW (in-flight)
  021-pill-generation.md                    # NEW (in-flight)
eval/test_cases/
  pill_agent.json                     # NEW
  redundancy_agent.json               # NEW
  semantic_agent.json                 # NEW
  delivery_agent.json                 # NEW
```

**Structure Decision**: Web application layout (Option 2 from the template) — backend (`src/platform_agent/`) + frontend (`frontend/`) — with the existing CLI (`src/platform_agent/__main__.py`) and Streamlit (`streamlit_app/`) preserved. New backend modules (`provisioning/`, `semantic/`, `workspace/`) follow the existing one-tool-per-file pattern. Patterns/agents from the migration-suite are **promoted from `patterns/migration-agent/`** into `src/platform_agent/provisioning/agents/` rather than re-implemented; the legacy `patterns/` tree remains as historical reference per the user input "wire it now."

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| Article V — accent palette extended beyond strict phData (`#1B2A4A` Navy / `#2563EB` Blue / `#0D9488` Teal / `#F97316` Orange) to include semantic status colors (success green, error red/amber) | Story 3's agent DAG and Story 6's Validation Card require unambiguous status semantics (active / complete / failed / ✓ / ✗). Phisha palette has only one warm and one cool accent, insufficient for 4–5 distinct status states without color-blind-unsafe palettes. | "Use existing palette only" rejected: status pulses on the DAG would be indistinguishable, undermining the "show your work" value (FR-028, FR-030). Resolution: limit additions to two semantic-only roles (success-green, error-amber), keep all chrome/typography/surfaces phData-strict, and document the additions in `docs/adr/020-provisioning-orchestration-iceberg.md` so the deviation is auditable. |
| Article VIII — SC-001 sets a single end-to-end demo at 8 minutes vs. the constitution's "under 3 minutes" guideline | SC-001 covers 7 user stories end-to-end (connect → discover → pill → redundancy → provision → validate → TTYD) — a multi-feature showcase, not a single-feature demo. Each individual story is demonstrable in under 3 minutes per its acceptance scenarios. | "Cut the showcase scope" rejected: the value of the platform IS the chained workflow; reducing the demo to one feature would bury the cross-source unification narrative. Resolution: SC-001 is the *full-narrative replay* metric; per-story demos remain under 3 minutes each. Documented as such in spec Story-level Independent Tests. |
| Promoting `patterns/migration-agent/` agents into `src/platform_agent/provisioning/` instead of keeping `patterns/` as the agent home | Provisioning is now an in-product flow (FR-027–FR-032), not a one-off migration utility. Strands agents must be importable by the FastAPI provisioning route without crossing the patterns/ boundary. | "Run agents from `patterns/` directly" rejected: that tree was a FAST template scaffold for standalone agent containers, not a library; cross-importing would re-introduce path hacks and break package layout. Resolution: agents move to `src/platform_agent/provisioning/agents/`, `patterns/` retained as a frozen historical reference. Documented in `docs/adr/020-provisioning-orchestration-iceberg.md`. |
