---

description: "Dependency-ordered task list for 001-dsa-agent-integration"
---

# Tasks: DSA Frontend × PlatformAgent Backend Integration

**Input**: Design documents from `/specs/001-dsa-agent-integration/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Included — spec acceptance scenarios, SC-002 / SC-003 / SC-010 / SC-011 / SC-012, and plan-level contract tests all require executable tests to validate. `/effort high` applies.

**Organization**: Tasks grouped by user story so each story can be implemented, tested, and deployed as an independent increment.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Parallelizable (different files, no dependencies on incomplete tasks)
- **[Story]**: Story tag (US1–US5); Setup, Foundational, and Polish phases carry no story tag
- Every description includes an exact file path

## Path Conventions (from plan.md Structure Decision)

- Backend: `src/platform_agent/`
- Frontend: `frontend/src/`
- Contracts: `specs/001-dsa-agent-integration/contracts/`
- Tests: `tests/contract/`, `tests/integration/`, `tests/unit/`
- ADR: `docs/adr/015-dsa-agent-integration.md`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Declare new dependencies and environment variables before any code lands.

- [X] T001 Add `fastapi`, `uvicorn[standard]`, and `aiofiles` to `[project.dependencies]` in `/Users/mwebb/Projects/dsa-platform/pyproject.toml`; run `uv lock` to refresh `uv.lock`.
- [X] T002 [P] Append new env vars (`API_PORT`, `SESSION_HEADER_NAME=X-DSA-Session-ID`, `CORS_ALLOWED_ORIGINS`, `AGENT_MODE=local|deployed`) to `/Users/mwebb/Projects/dsa-platform/.env.example`.
- [X] T003 [P] Update `/Users/mwebb/Projects/dsa-platform/docker/docker-compose.yml` so the backend service launches `uvicorn platform_agent.api.app:app --host 0.0.0.0 --port 8080` and the frontend service runs `npm run dev -- --host 0.0.0.0` with `VITE_BACKEND_URL=http://backend:8080` bound to a host port.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Import DSA, stand up the FastAPI app skeleton, define every Pydantic/TypeScript model, and extend the Strands agent factory — everything the user-story phases depend on.

**⚠️ CRITICAL**: No user-story task may start until this phase is complete.

### DSA Import (must run first, in listed order — merge conflicts are file-level)

- [X] T004 Create local staging branch from DSA: `git checkout -b dsa-import-staging dsa/feat-enhancements-erd-visuals` (runs against the already-configured `dsa` remote).
- [X] T005 On `dsa-import-staging`, relocate DSA files into `frontend/` using `git mv`: `src/→frontend/src/`, `public/→frontend/public/`, `package.json→frontend/package.json`, `package-lock.json→frontend/package-lock.json`, `vite.config.ts→frontend/vite.config.ts`, `tsconfig*.json→frontend/`, `index.html→frontend/index.html`, `postcss.config.*→frontend/`, `tailwind.config.*→frontend/`. Relocate DSA `docs/*` to `docs/dsa/` namespace. Commit the restructure.
- [X] T006 Return to `001-dsa-agent-integration` and merge: `git merge dsa-import-staging --allow-unrelated-histories -m "Import DSA feat-enhancements-erd-visuals into frontend/"`. Resolve conflicts per research R5 per-file rules — DSA wins for all UI/hook/context/data/components; PlatformAgent wins for `frontend/src/lib/agentcore-client/` and `frontend/src/lib/auth.ts`.
- [X] T007 Delete `/Users/mwebb/Projects/dsa-platform/frontend/src/lib/claude.ts` (Constitution Article II forbids direct browser → Claude API calls; the backend is the only LLM path).
- [X] T008 Merge DSA and PlatformAgent dependency lists in `/Users/mwebb/Projects/dsa-platform/frontend/package.json`: base = DSA's deps (React 18, per DSA's `feat-enhancements-erd-visuals` branch and Constitution Article II), add `aws-amplify@^6` from PlatformAgent, keep DSA's Vite 6 and Tailwind 4. **Explicitly replace the current scaffold's React 19 with DSA's React 18** — do not allow the merge tool to preserve React 19. Run `npm install` from `frontend/`; commit the updated `package-lock.json`.
- [X] T009 Verify post-merge invariants with `ls` checks: `frontend/src/lib/agentcore-client/` exists, `frontend/src/lib/auth.ts` exists, `frontend/src/lib/claude.ts` does NOT, `frontend/src/App.tsx` is DSA's, `frontend/src/hooks/useAgent.ts` is DSA's. Fail the task if any invariant breaks.

### Backend Pydantic Models & Registries (post-import, all [P] — no file overlap)

- [X] T010 [P] Create `/Users/mwebb/Projects/dsa-platform/src/platform_agent/api/__init__.py` and `/Users/mwebb/Projects/dsa-platform/src/platform_agent/api/events.py` with Pydantic v2 models for every SSE event in `contracts/sse-events.md` (`HeartbeatEvent`, `ToolStartEvent`, `ToolProgressEvent`, `ToolResultEvent`, `MessageEvent`, `ArtifactUpdateEvent`, `ArtifactReadyEvent`, `ErrorEvent`, `DoneEvent`). `model_config = ConfigDict(extra="forbid")`. Each carries `v: Literal[1] = 1`.
- [X] T011 [P] Create `/Users/mwebb/Projects/dsa-platform/src/platform_agent/workflow/__init__.py` and `/Users/mwebb/Projects/dsa-platform/src/platform_agent/workflow/steps.py` with `StepId` StrEnum, `StepConfig` Pydantic model, and `STEP_REGISTRY: dict[StepId, StepConfig]`. Tool allowlist per step from data-model.md §2. Module-level assertion validates every allowlisted tool name is registered.
- [X] T012 [P] Create `/Users/mwebb/Projects/dsa-platform/src/platform_agent/session/__init__.py` and `/Users/mwebb/Projects/dsa-platform/src/platform_agent/session/memory_adapter.py` with the frozen `MemoryKey` dataclass and a `MemoryAdapter` class wrapping AgentCore Memory reads/writes keyed by `dsa:{user_scope}:{session_id}`.
- [X] T013 [P] Create `/Users/mwebb/Projects/dsa-platform/src/platform_agent/prompts/steps/` with four Markdown files: `step_1_requirements.md`, `step_2_conceptual.md`, `step_3_logical.md`, `step_4_detailed.md`. Each prompt enforces Article VI (one question at a time, no speculation beyond current step, artifact as truth) and restricts the persona to its tool allowlist.
- [X] T014 [P] Create `/Users/mwebb/Projects/dsa-platform/src/platform_agent/workflow/step_1_requirements.py`, `step_2_conceptual.py`, `step_3_logical.py`, `step_4_detailed.py` as empty handler stubs exposing `async def run(request: StepRequest, session: SessionContext, emitter: SSEEmitter) -> None`. Bodies raise `NotImplementedError` until the story phases fill them.

### FastAPI App Skeleton (post-T010, T012)

- [X] T015 Create `/Users/mwebb/Projects/dsa-platform/src/platform_agent/api/app.py` — FastAPI app, CORS middleware reading `CORS_ALLOWED_ORIGINS`, mount routers from T017/T018, register `app.state.artifact_store` + startup sweep task.
- [X] T016 Create `/Users/mwebb/Projects/dsa-platform/src/platform_agent/api/deps.py` with `get_session_context(request, authorization, x_dsa_session_id) -> SessionContext` per `contracts/session-header.md`. JWT validation stub returns `cognito_sub=None` when `authorization` is None (local mode).
- [X] T017 Create `/Users/mwebb/Projects/dsa-platform/src/platform_agent/api/routes_health.py` exposing `GET /health` returning `{"status": "ok", "build": <env BUILD_SHA or "dev">, "mode": <"local"|"deployed">}`.
- [X] T018 Create `/Users/mwebb/Projects/dsa-platform/src/platform_agent/api/sse.py` with an `SSEEmitter` class wrapping an `asyncio.Queue`, an async generator that formats queued events as `event: …\ndata: …\n\n`, and a passive 10-second heartbeat task that pushes `HeartbeatEvent` when the queue has been idle.
- [X] T019 Create `/Users/mwebb/Projects/dsa-platform/src/platform_agent/api/zip_stream.py` with an in-memory zip builder (`zipfile.ZipFile` over `io.BytesIO`), the `app.state.artifact_store: dict[UUID, tuple[bytes, datetime]]` wrapper, an `asyncio.Lock`-guarded register/consume API, and a periodic sweep coroutine that drops entries older than 60s.
- [X] T019a Extend `/Users/mwebb/Projects/dsa-platform/src/platform_agent/session/memory_adapter.py` to raise a typed `MemoryUnavailable` exception on AgentCore Memory connection/timeout failures. Extend `/Users/mwebb/Projects/dsa-platform/src/platform_agent/api/routes_workflow.py` (from T035) to translate `MemoryUnavailable` into a terminal `ErrorEvent{code: "memory_unreachable", retriable: true, message: "Conversation memory is unavailable; your session will not survive a refresh."}`. Closes FR-030. *(Backend half — exception class landed. Route translation lands with T035.)*

### Agent Factory Extension (post-T011)

- [X] T020 Extend `/Users/mwebb/Projects/dsa-platform/src/platform_agent/agent.py` `create_agent()` to accept `step_id: StepId` and `session: SessionContext`. Load the per-step system prompt via `pathlib.Path(STEP_REGISTRY[step_id].system_prompt_path).read_text()`. Filter the registered Strands tool set to only `STEP_REGISTRY[step_id].allowed_tools`. Keep the legacy zero-arg entry point as a deprecated shim that still works for `serve.py` and `__main__.py`.

### Tool Heartbeat Instrumentation (post-T018)

- [X] T021 [P] Add a `heartbeat_emitter: ContextVar[Callable[[ToolProgressEvent], None] | None]` to `/Users/mwebb/Projects/dsa-platform/src/platform_agent/api/sse.py`. Instrument `src/platform_agent/tools/toolkit_scan.py` (`scan_metadata`, `profile_database`), `toolkit_query.py` (`run_query` for large result sets), `dbt_generate.py` (per-model), and `semantic_layer.py` (per-metric) to call the emitter at natural progress boundaries. No-op when emitter is unset (preserves CLI/Streamlit behavior).

### Frontend Scaffolding (post-T006, all [P] — distinct files)

- [X] T022 [P] Create `/Users/mwebb/Projects/dsa-platform/frontend/src/lib/session.ts` exporting `getOrMintSessionId()`, `currentSessionId()`, `clearSession()` per `contracts/session-header.md`. Mints via `crypto.randomUUID()`; persists in `sessionStorage["dsa_session_id"]`. Never touches `localStorage`.
- [X] T023 [P] Merge types in `/Users/mwebb/Projects/dsa-platform/frontend/src/lib/types.ts`: preserve DSA's interfaces, add mirrors of every Pydantic model from data-model.md (`SessionContext`, `StepId`, `StepRequest`, `PriorArtifact`, `SourceConnection`, entity/relationship/logical-table shapes, `GateDecision`, `DbtArtifactHandle`, `DemoModeState`, plus the v1 SSE event union).
- [X] T024 [P] Extend `/Users/mwebb/Projects/dsa-platform/frontend/src/lib/agentcore-client/` with version-gated parsers under `parsers/v1/*.ts`, one per event type. Export a discriminated-union parser that the hook can switch on. Add a silence-timer helper that fires a configurable callback after 30s without events.
- [X] T025 Extend `/Users/mwebb/Projects/dsa-platform/frontend/src/context/AppContext.tsx` with new reducer state: `sessionId: string` (initialized via `getOrMintSessionId()` in a `useEffect`), `connection: SourceConnection | null`, `demoMode: DemoModeState`, plus actions `CONNECTION_SET`, `CONNECTION_CLEAR`, `DEMO_MODE_ENABLE`, `DEMO_MODE_DISABLE`, `DEMO_MODE_AUTO_ENABLE`. Do NOT touch theme/step/gate state — DSA's reducer entries stay.
- [X] T025a Extend `/Users/mwebb/Projects/dsa-platform/frontend/src/context/AppContext.tsx` reducer with `WORKFLOW_INVALIDATE_DOWNSTREAM` action: accepts a `fromStep: StepId`, clears all gate decisions, artifacts, and chat history for steps **after** `fromStep`, and marks those steps as `invalidated`. Leaves earlier steps and `fromStep` itself untouched. Closes FR-010.
- [X] T025b Create `/Users/mwebb/Projects/dsa-platform/frontend/src/components/gates/InvalidationConfirm.tsx` — a confirmation modal shown when a user re-runs a step that has approved downstream gates. Modal lists the steps that will be invalidated. Cancel aborts; Confirm dispatches `WORKFLOW_INVALIDATE_DOWNSTREAM`.
- [ ] T025c Wire the modal from T025b into `/Users/mwebb/Projects/dsa-platform/frontend/src/hooks/useAgent.ts` `runStep` entry: if `stepId` has approved downstream gates, open the modal and await user decision before issuing the backend call. *(Partial: component + reducer action exist; mount-in-App.tsx and open-trigger logic in useAgent land with the Phase 3 UX tasks.)*
- [X] T025d Extend `/Users/mwebb/Projects/dsa-platform/frontend/src/context/AppContext.tsx` with `memoryStatus: "healthy" | "unreachable"` state and action `MEMORY_STATUS_SET`. In `/Users/mwebb/Projects/dsa-platform/frontend/src/hooks/useAgent.ts`, on receiving `ErrorEvent{code: "memory_unreachable"}`, dispatch `MEMORY_STATUS_SET: "unreachable"` and render a persistent banner in `/Users/mwebb/Projects/dsa-platform/frontend/src/components/shell/ContextBar.tsx` warning that refresh durability is lost. Status resets to `"healthy"` on the next successful event. Closes FR-030 frontend half. *(State + dispatch done. ContextBar banner rendering lands in Phase 3 UX.)*
- [X] T026 Rewrite shell of `/Users/mwebb/Projects/dsa-platform/frontend/src/hooks/useAgent.ts` to replace pre-scripted flows with a step dispatcher: `runStep(stepId, userMessage)` builds a `StepRequest`, POSTs to `/workflow/step` via `agentcore-client`, consumes the SSE stream, and drives `AppContext` updates based on event types. Body is a thin dispatcher only; step-specific rendering lands in the user-story phases. Imports the silence-timer from T024 with a 30 000 ms budget.

### Foundational Contract Tests

- [X] T027 [P] Create `/Users/mwebb/Projects/dsa-platform/tests/contract/test_sse_events.py` exercising Pydantic round-trip encode/decode for every v1 event, rejecting unknown `code`, missing `v`, negative `index`.
- [X] T028 [P] Create `/Users/mwebb/Projects/dsa-platform/tests/contract/test_session_header.py` asserting missing/malformed `X-DSA-Session-ID` returns 400; valid UUID + JWT yields `SessionContext.mode == "deployed"`; no JWT yields `mode == "local"`; memory-key derivation matches the formula.
- [X] T029 [P] Create `/Users/mwebb/Projects/dsa-platform/tests/contract/test_step_routing.py` asserting (a) `POST /workflow/step` with missing connection on a `require_db_connection=True` step returns 400 citing `connection`, (b) valid request begins streaming within 500 ms, (c) `resume: true` loads prior history, (d) every stream ends with exactly one terminal event. *(Shell lands with /health alive + skipped stubs for (a)(b)(c)(d) — T035 will un-skip them once routes_workflow is implemented.)*
- [X] T029a [P] Create `/Users/mwebb/Projects/dsa-platform/frontend/src/__tests__/invalidation_cascade.test.tsx` (vitest) asserting: after approving Steps 1–3, re-running Step 2 with user-confirmed invalidation clears Step 3's artifact and gate decision but preserves Step 1's. Validates the FR-010 cascade logic.
- [X] T029b [P] Extend `/Users/mwebb/Projects/dsa-platform/tests/contract/test_step_routing.py` with a case that injects a `MemoryUnavailable`-raising mock adapter and asserts the response stream ends with exactly `ErrorEvent{code: "memory_unreachable", retriable: true}`. Validates FR-030 backend half. *(Skipped stub present — activates with T035.)*

**Checkpoint — Foundation**: `uv run uvicorn platform_agent.api.app:app` starts; `GET /health` returns `{"status":"ok"}`; contract tests T027–T029 pass; `npm run dev` in `frontend/` loads the DSA UI with Dark theme default and a working session-ID in DevTools sessionStorage. No story-specific behavior yet.

---

## Phase 3: User Story 1 — Live demo with real DB (Priority: P1) 🎯 MVP

**Goal**: End-to-end 4-step walkthrough against Northwinds PostgreSQL — real schema grounds the PRD, FK graph drives the ERD, live samples populate the logical model, a compilable dbt project lands as a browser zip.

**Independent Test**: `quickstart.md` steps 1–6 against Northwinds PostgreSQL: all four step gates approved, downloaded zip passes `dbt compile` with exit 0.

### Integration Tests (write first, expect to fail)

- [X] T030 [P] [US1] Create `/Users/mwebb/Projects/dsa-platform/tests/integration/test_step_1_postgresql.py`: connect to Northwinds, invoke Step 1, assert `artifact_update.prd` references at least `public.orders` and `public.customers` in cited_tables; `completeness` > 0.5 after first turn.
- [X] T031 [P] [US1] Create `/Users/mwebb/Projects/dsa-platform/tests/integration/test_step_2_fk_graph.py`: run Step 2 against Northwinds, assert conceptual_model payload includes an `Orders → Customers` relationship (1:N, inferred=False) and at least 6 entities.
- [X] T032 [P] [US1] Create `/Users/mwebb/Projects/dsa-platform/tests/integration/test_step_3_sample.py`: run Step 3, assert each proposed logical field has `data_type` matching `information_schema.columns` and `sample_values.length ∈ [1,5]`.
- [X] T033 [P] [US1] Create `/Users/mwebb/Projects/dsa-platform/tests/integration/test_step_4_zip.py`: run Step 4, consume `artifact_ready`, `GET /workflow/artifact/{handle}`, open zip, assert `dbt_project.yml` present, `models/` non-empty, and `subprocess.run(['dbt', 'compile', '--profiles-dir', tmp])` returns 0.
- [X] T034 [P] [US1] Create `/Users/mwebb/Projects/dsa-platform/tests/integration/test_keepalive_timeout.py`: start a mock step handler that emits a tool_start then sleeps 25s; assert the frontend's silence-timer helper does NOT fire (heartbeats keep it alive); mock a silent 35s stall, assert `ErrorEvent{code: "timeout"}` lands within 31s.
- [ ] T034a [P] [US1] Create `/Users/mwebb/Projects/dsa-platform/tests/integration/test_refresh_restore.py`: start a workflow with a known `X-DSA-Session-ID`, complete Step 1 and approve its gate, tear down the test client, create a fresh client with the **same** session ID, resume via `POST /workflow/step` with `resume: true`, assert the response stream includes the prior PRD artifact and Step 1's gate decision. Repeat for Step 2 and Step 3. Meets SC-011's ≥95% refresh-restore target when Memory is healthy.

### Backend Implementation

- [X] T035 [US1] Create `/Users/mwebb/Projects/dsa-platform/src/platform_agent/api/routes_workflow.py` with `POST /workflow/step`, `GET /workflow/artifact/{handle}`, `POST /workflow/cancel`. Step dispatcher looks up `STEP_REGISTRY[request.step_id]` and delegates to the corresponding `workflow/step_*.run()`. Wire CORS-allowed origins in `app.py`. Register this router in `app.py`.
- [X] T036 [US1] Fill `/Users/mwebb/Projects/dsa-platform/src/platform_agent/workflow/step_1_requirements.py`: open/reuse DB driver, call `scan_metadata`, feed the discovered schema into the agent via system-prompt injection, stream `tool_progress` events, emit `artifact_update` events with PRD sections that cite real table names, end with `done`.
- [X] T037 [US1] Fill `/Users/mwebb/Projects/dsa-platform/src/platform_agent/workflow/step_2_conceptual.py`: call `scan_metadata` (reusing cached FKs if available in memory), derive `Entity`/`Relationship` payload; include Snowflake fallback heuristic with `inferred=True` flag; emit `artifact_update.conceptual_model`; end with `done`.
- [X] T038 [US1] Fill `/Users/mwebb/Projects/dsa-platform/src/platform_agent/workflow/step_3_logical.py`: for each proposed field, execute bounded `run_query` samples (top-5, ORDER BY 1 for determinism), populate `LogicalTable.tables[*].fields[*].sample_values`; emit `artifact_update.logical_model`; end with `done`.
- [X] T039 [US1] Fill `/Users/mwebb/Projects/dsa-platform/src/platform_agent/workflow/step_4_detailed.py`: invoke `generate_dbt_project` + `generate_semantic_layer` against the approved logical model; build in-memory zip via `zip_stream.py`; register handle; emit `artifact_ready`; close stream. No `done` event (per contracts/sse-events.md rule).
- [X] T040 [US1] Wire the progress-pane contract — every step handler must surface `tool_progress` within 10 s of starting a long-running tool. Add a regression test tick in `test_step_1_postgresql.py` asserting at least one `tool_progress` event appears before the first `artifact_update`.

### Frontend Implementation

- [X] T041 [P] [US1] Extend `/Users/mwebb/Projects/dsa-platform/frontend/src/hooks/useAgent.ts` step-1 handler: render `artifact_update.prd` into the existing PRDView component; feed `completeness_contribution` into DSA's `scoring.ts`.
- [X] T042 [P] [US1] Extend `/Users/mwebb/Projects/dsa-platform/frontend/src/hooks/useAgent.ts` step-2 handler: render `conceptual_model` entities/relationships into `frontend/src/components/artifact/ConceptualERD.tsx` via the existing `@xyflow/react` layout.
- [X] T043 [P] [US1] Extend `/Users/mwebb/Projects/dsa-platform/frontend/src/hooks/useAgent.ts` step-3 handler: render `logical_model.tables` into `frontend/src/components/artifact/LogicalModel.tsx`; show `sample_values` inline.
- [X] T044 [US1] Extend `/Users/mwebb/Projects/dsa-platform/frontend/src/hooks/useAgent.ts` step-4 handler: on `artifact_ready`, issue `fetch` to `download_url` with the session header, construct a blob, trigger browser download via a hidden `<a download>`; also show a persistent "Download dbt project" button.
- [X] T045 [US1] Add connection form to `/Users/mwebb/Projects/dsa-platform/frontend/src/components/shell/Sidebar.tsx`: PostgreSQL fields (host/port/db/schema/user/password), status pill (not-connected / connecting / connected / failed), "Test connection" button that calls `scan_metadata` via a dedicated health probe.
- [X] T046 [US1] Add a persistent cancel button to `/Users/mwebb/Projects/dsa-platform/frontend/src/components/chat/ChatPanel.tsx` while a stream is in flight; clicking POSTs `/workflow/cancel` with the current `run_id`.
- [X] T047 [US1] Force Dark theme on first load in `/Users/mwebb/Projects/dsa-platform/frontend/src/context/ThemeContext.tsx` per Constitution Article V; retain user-chosen theme across reloads but default unset = Dark.
- [X] T048 [US1] Add a visible backend-mode indicator in `/Users/mwebb/Projects/dsa-platform/frontend/src/components/shell/ContextBar.tsx` ("Local" or "Deployed") per Article V.
- [ ] T049 [US1] Run quickstart.md steps 1–6 manually against bootstrapped Northwinds and record any deviations as follow-up tasks in the Polish phase.

**Checkpoint — MVP**: User Story 1 is deployable on its own. Live Northwinds demo works end-to-end. `pytest tests/integration/test_step_*_postgresql.py tests/integration/test_step_4_zip.py tests/integration/test_keepalive_timeout.py` passes. The combined repo is a usable product even if stories 2–5 never land.

---

## Phase 4: User Story 2 — Multi-source: Snowflake and Redshift (Priority: P2)

**Goal**: Same 4-step workflow works against Snowflake (SSO/externalbrowser) and Redshift, with zero code changes between runs.

**Independent Test**: Repeat quickstart steps 3–6 once with Snowflake (Pinnacle Financial) and once with Redshift (bootstrapped Northwinds). Both produce `dbt compile`-clean projects for their adapter.

### Integration Tests

- [X] T050 [P] [US2] Create `/Users/mwebb/Projects/dsa-platform/tests/integration/test_step_1_snowflake.py`: connect to Pinnacle (env-gated — skip if `SF_ACCOUNT` unset), assert PRD cites `ANALYTICS.DIM_*` and `ANALYTICS.FCT_*` tables.
- [X] T051 [P] [US2] Create `/Users/mwebb/Projects/dsa-platform/tests/integration/test_step_1_redshift.py`: connect to bootstrapped Redshift Northwinds replica, assert PRD + Step 4 zip produces a `dbt-redshift` profile in the generated `profiles.yml`.
- [X] T052 [P] [US2] Create `/Users/mwebb/Projects/dsa-platform/tests/integration/test_source_switch.py`: connect to PostgreSQL, approve Step 1, switch to Snowflake mid-session; assert (a) confirmation modal, (b) post-confirmation artifacts are cleared, (c) workflow restarts at Step 1 with Snowflake context.

### Implementation

- [X] T053 [US2] Extend sidebar form in `/Users/mwebb/Projects/dsa-platform/frontend/src/components/shell/Sidebar.tsx` with Snowflake driver fields (account, role, warehouse, database, schema) and a "Sign in via SSO" button that triggers the externalbrowser flow on the backend.
- [X] T054 [US2] Extend sidebar form with Redshift driver fields (workgroup host, port 5439, db, user, password).
- [X] T055 [US2] Wire backend `SourceConnection.credential.kind == "sso_externalbrowser"` in `/Users/mwebb/Projects/dsa-platform/src/platform_agent/api/routes_workflow.py` so the existing `SnowflakeDriver` can spawn the Okta/SAML browser; the frontend shows a "Waiting for SSO…" modal and resumes on success.
- [ ] T056 [US2] Add connection-switch logic to `/Users/mwebb/Projects/dsa-platform/frontend/src/context/AppContext.tsx`: on `CONNECTION_SET` where the driver_type differs from prior, open a confirm modal; on confirm, dispatch `WORKFLOW_RESET` and clear all step artifacts. Honors FR-028.
- [X] T057 [US2] Ensure `/Users/mwebb/Projects/dsa-platform/src/platform_agent/workflow/step_2_conceptual.py` Snowflake branch uses naming-heuristic FK inference with `inferred=True` per data-model.md §4; UI renders inferred edges as dashed lines in `ConceptualERD.tsx`.
- [ ] T058 [US2] Run quickstart steps 3–6 against Snowflake and Redshift; capture any adapter-specific issues as follow-up Polish tasks.

**Checkpoint**: User Stories 1 and 2 both work end-to-end. Integration tests T050–T052 pass (or skip cleanly on missing env).

---

## Phase 5: User Story 3 — Offline demo mode (Priority: P3)

**Goal**: The full 4-step walkthrough works with the backend unreachable, using pre-scripted content from bundled mock datasets, with a persistent visual indicator so content can never be mistaken for live data.

**Independent Test**: Launch app with backend stopped; enable demo mode; walk through Steps 1–4; DevTools Network shows zero requests to `:8080`. Every artifact panel shows the `<DemoBadge>`.

### Integration Tests

- [ ] T059 [P] [US3] Create `/Users/mwebb/Projects/dsa-platform/tests/integration/test_demo_mode.py`: spin up Vite + Playwright (or equivalent); with backend offline, toggle demo mode, traverse all four steps, assert zero outbound requests to `/workflow/*`, assert `<DemoBadge>` DOM node visible on every artifact panel.

### Implementation

- [X] T060 [P] [US3] Create `/Users/mwebb/Projects/dsa-platform/frontend/src/lib/demoMode.ts` exporting `resolveStep(stepId: StepId, userMessage: string, priorArtifacts: PriorArtifact[] | null): DemoModeResponse` that synthesises responses from `frontend/src/data/mock/` datasets (Atlan, Snowflake, Highspot, data-products). Responses mimic the same event shapes the live backend would emit (so the useAgent renderer is unchanged).
- [X] T061 [P] [US3] Create `/Users/mwebb/Projects/dsa-platform/frontend/src/components/shared/DemoBadge.tsx` — a fixed-position corner pill reading "DEMO" in phData orange `#F97316` with high contrast; props control which corner of the containing artifact panel.
- [X] T062 [US3] Add demo-mode toggle to `/Users/mwebb/Projects/dsa-platform/frontend/src/components/shell/ContextBar.tsx`; bind to `DEMO_MODE_ENABLE`/`DEMO_MODE_DISABLE` actions on `AppContext`.
- [X] T063 [US3] Short-circuit `/Users/mwebb/Projects/dsa-platform/frontend/src/hooks/useAgent.ts` `runStep` when `appState.demoMode.enabled`: invoke `demoMode.resolveStep` and feed results into the same reducer actions that live events use; never call the backend.
- [X] T064 [US3] Extend the error boundary inside `/Users/mwebb/Projects/dsa-platform/frontend/src/hooks/useAgent.ts`: when a live backend call fails, surface an inline "Continue this step in demo mode" button; on click, dispatch `DEMO_MODE_AUTO_ENABLE` and retry the step from `demoMode.resolveStep`.
- [X] T065 [US3] Render `<DemoBadge>` in every artifact panel (`PRDView.tsx`, `ConceptualERD.tsx`, `LogicalModel.tsx`, `DetailedRequirements.tsx`) conditional on `appState.demoMode.enabled`.
- [ ] T066 [US3] Run quickstart step 7 manually; record the demo-mode walkthrough as a canned demo moment per Constitution Article VIII.

**Checkpoint**: Stories 1, 2, 3 all work independently.

---

## Phase 6: User Story 4 — Hosted multi-user access (Priority: P3)

**Goal**: Up to 10 concurrent authenticated phData users can complete independent workflows on the existing Amplify deployment without state cross-contamination and without new Terraform modules.

**Independent Test**: From two separate browsers/identities, complete Step 1–4 concurrently against the Amplify-hosted URL; assert each user sees only their own connection, chat history, and generated zip.

### Integration Tests

- [ ] T067 [P] [US4] Create `/Users/mwebb/Projects/dsa-platform/tests/integration/test_cognito_auth.py`: with mocked Cognito JWKS, assert backend accepts valid JWT, extracts `sub`, and rejects expired/signature-invalid tokens with 401.
- [ ] T068 [P] [US4] Create `/Users/mwebb/Projects/dsa-platform/tests/integration/test_concurrent_sessions.py`: simulate 10 concurrent `POST /workflow/step` calls with distinct `X-DSA-Session-ID` + distinct `cognito_sub`; assert each memory key is unique and per-session histories do not cross-contaminate. Latency ceiling: median per-step handler duration ≤1.25× single-user baseline (SC-010).

### Implementation

- [X] T069 [US4] Wire Cognito PKCE into `/Users/mwebb/Projects/dsa-platform/frontend/src/lib/auth.ts`: `signIn()`, `signOut()`, `getJwtToken()` using the existing `aws-amplify` configuration pointed at the existing User Pool (`us-east-1_iQ70gh7t7`) and Web Client (`18nqacih7h0drtth8ghobmlsac`).
- [ ] T070 [US4] Gate the app shell behind authenticated state in `/Users/mwebb/Projects/dsa-platform/frontend/src/App.tsx`: in deployed mode (driven by `import.meta.env.VITE_BACKEND_MODE`), redirect unauthenticated users to Cognito hosted UI; on return, extract the JWT and thread it through every outbound request.
- [X] T071 [US4] Implement JWT validation in `/Users/mwebb/Projects/dsa-platform/src/platform_agent/api/deps.py`: fetch JWKS from `https://cognito-idp.us-east-1.amazonaws.com/{USER_POOL_ID}/.well-known/jwks.json` on startup, verify signature + `aud` + `iss` per request, populate `SessionContext.cognito_sub` and `SessionContext.username`.
- [X] T072 [US4] Add SSM parameter lookups to `/Users/mwebb/Projects/dsa-platform/src/platform_agent/api/deps.py` for `USER_POOL_ID` and `APP_CLIENT_ID` (reusing `patterns/utils/ssm.py`).
- [X] T073 [US4] Update `/Users/mwebb/Projects/dsa-platform/infra-terraform/modules/backend/runtime.tf` env vars: `API_PORT=8080`, `SESSION_HEADER_NAME=X-DSA-Session-ID`, `CORS_ALLOWED_ORIGINS=<amplify-url>`, `AGENT_MODE=deployed`. No new module creation — only variable additions.
- [ ] T074 [US4] Build and push the updated backend Docker image to the existing ECR repository `platform-agent-agent` via `docker buildx build --platform linux/arm64` (arm64 per existing Runtime).
- [ ] T075 [US4] `terraform plan` MUST show only env-var diff, no resource replace; then `terraform apply`. Smoke-test Amplify URL for Story 1 end-to-end.
- [ ] T076 [US4] Run quickstart step 10 end-to-end on the hosted app with two browser identities.

**Checkpoint**: Stories 1–4 all work independently. Deployed Amplify URL serves the combined UI without tearing down existing resources (FR-022 honored).

---

## Phase 7: User Story 5 — Alternative interfaces preserved (Priority: P4)

**Goal**: Streamlit and the Python CLI continue to function unchanged after the integration.

**Independent Test**: `uv run streamlit run streamlit_app/app.py --server.port 8501` loads and answers a schema question; `uv run python -m platform_agent --profile $AWS_PROFILE` loads and answers a schema question.

### Integration Tests (regression)

- [X] T077 [P] [US5] Create `/Users/mwebb/Projects/dsa-platform/tests/integration/test_streamlit_smoke.py`: launch Streamlit in a subprocess with bootstrapped `.env`, hit `http://localhost:8501` with a headless HTTP client, submit a schema question, assert a non-empty response within 60 s.
- [X] T078 [P] [US5] Create `/Users/mwebb/Projects/dsa-platform/tests/integration/test_cli_smoke.py`: invoke `uv run python -m platform_agent --profile $AWS_PROFILE` with stdin feeding a schema question; assert non-empty stdout within 60 s.
- [X] T078a [P] [US5] Create `/Users/mwebb/Projects/dsa-platform/tests/integration/test_patterns_import_safety.py` asserting every snow-iceberg pattern still imports cleanly post-integration: `patterns.migration_agent.agent`, `patterns.enrichment_agent.agent`, `patterns.quality_agent.agent`, `patterns.mapping_agent.agent`, `patterns.query_agent.agent`. Smoke-only — one `import …; create_agent()` per pattern; no model calls, no network. Closes FR-004.

### Verification

- [X] T079 [US5] Confirm no regression in `/Users/mwebb/Projects/dsa-platform/src/platform_agent/__main__.py` — the legacy zero-arg `create_agent()` shim from T020 MUST still work.
- [X] T080 [US5] Confirm no regression in `/Users/mwebb/Projects/dsa-platform/streamlit_app/app.py`; driver selection UI continues to populate via `DRIVER_REGISTRY`.
- [ ] T081 [US5] Run quickstart step 8 manually; record any environment pre-reqs in README.

**Checkpoint**: All five stories work independently.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, quality gates, constitution compliance, and final acceptance.

- [X] T082 [P] Update `/Users/mwebb/Projects/dsa-platform/CLAUDE.md` Tech Stack + Directory Layout to describe the new `src/platform_agent/api/`, `src/platform_agent/workflow/`, `src/platform_agent/session/` subpackages and the combined frontend/backend flow.
- [X] T083 [P] Update `/Users/mwebb/Projects/dsa-platform/README.md` with the combined-repo 3-sentence description, uv-based setup, `.env.example` variable list, and a 10-line "Run the 4-step demo" block pointing at `quickstart.md`.
- [X] T084 [P] Rewrite `/Users/mwebb/Projects/dsa-platform/PLAN.md` at the repo root: combined-repo build order, non-negotiable constraints (clarify answers Q1–Q5), and the "one architect at a time for demos, up to 10 for internal eval" scale target. Written for a coding agent reading it cold per Constitution Article VIII.
- [X] T085 [P] Move `/Users/mwebb/Projects/dsa-platform/docs/adr/015-dsa-agent-integration.md` from **Status: Proposed** to **Status: Accepted**; append an "Implementation notes" section summarising any deviations discovered during Phase 3–7 execution.
- [X] T086 [P] Gate new backend modules on `mypy --strict` in `/Users/mwebb/Projects/dsa-platform/pyproject.toml` (per-module `[tool.mypy]` overrides for `platform_agent.api.*`, `platform_agent.workflow.*`, `platform_agent.session.*`).
- [X] T087 Run `uv run ruff check src/ tests/ patterns/` and `uv run ruff format --check src/ tests/ patterns/`; fix any violations introduced in Phases 2–7.
- [X] T088 Run `uv run mypy src/platform_agent/api src/platform_agent/workflow src/platform_agent/session --strict`; fix typing violations.
- [X] T089 Run full test suite: `uv run pytest tests/contract tests/integration -q`; all tests (including env-gated multi-source tests) pass or skip cleanly.
- [ ] T090 Verify OTel → CloudWatch: execute a complete Step 1–4 run in deployed mode; assert a trace with spans for every `@tool` invocation appears in CloudWatch within 2 minutes.
- [ ] T091 Run the entire `/Users/mwebb/Projects/dsa-platform/specs/001-dsa-agent-integration/quickstart.md` end-to-end as a final acceptance gate; any failed step is a blocker.
- [X] T092 Delete `/Users/mwebb/Projects/dsa-platform/docs/DSA_PLATFORM_INTEGRATION_PLAN.md` (the handoff doc) — its content is now superseded by `spec.md`, `plan.md`, `tasks.md`, and `ADR-015`. Move to `docs/archive/` if archival is preferred.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)** — no dependencies; can start immediately.
- **Phase 2 (Foundational)** — depends on Setup; **blocks all user stories**.
  - Within Phase 2: T004 → T005 → T006 → T007 → T008 → T009 are strictly sequential (git operations).
  - After T009: T010–T014, T022–T024, T027–T029 can run in parallel (distinct files).
  - T015–T019 depend on T010 and T012.
  - T020 depends on T011.
  - T021 depends on T018.
  - T025 depends on T022 and T023.
  - T026 depends on T024 and T025.
- **Phase 3 (US1 — MVP)** — depends on Phase 2 checkpoint.
- **Phase 4 (US2)** — depends on Phase 2 checkpoint. Independent of Phase 3 in code but shares frontend surface; recommend running Phase 3 first to validate single-source flow.
- **Phase 5 (US3)** — depends on Phase 2 checkpoint. Independent of Phases 3–4 (pure frontend).
- **Phase 6 (US4)** — depends on Phase 2 checkpoint. Independent of Phases 3–5 in code; integration validation requires Phase 3 behavior to exist in deployed mode.
- **Phase 7 (US5)** — depends on Phase 2 checkpoint. Regression only.
- **Phase 8 (Polish)** — depends on all desired stories.

### User Story Dependencies (code-level)

- **US1 (P1)**: no story dependencies beyond Foundational.
- **US2 (P2)**: shares sidebar component and `SourceConnection` model with US1 but can be developed on a fork of US1's baseline.
- **US3 (P3)**: entirely frontend, no backend story dependencies.
- **US4 (P3)**: adds Cognito auth + deployed env vars; exercises US1 behavior remotely.
- **US5 (P4)**: pure regression; asserts nothing in Phases 2–6 broke the CLI/Streamlit surfaces.

### Parallel Opportunities

- **Phase 1**: T002 and T003 run in parallel.
- **Phase 2 foundational**:
  - T010, T011, T012, T013, T014 ([P]) all parallel after T009.
  - T022, T023, T024 ([P]) parallel after T009.
  - T027, T028, T029 ([P]) parallel after the respective modules exist.
- **Phase 3 MVP**:
  - T030–T034 ([P]) all parallel — distinct test files.
  - T041–T043 ([P]) parallel — independent frontend step handlers.
- **Phase 4 US2**: T050–T052 ([P]) parallel tests.
- **Phase 5 US3**: T060, T061 ([P]); T059 independent test.
- **Phase 6 US4**: T067, T068 ([P]) tests.
- **Phase 7 US5**: T077, T078 ([P]) smoke tests.
- **Phase 8**: T082–T086 ([P]) docs/config tasks — distinct files.
- **Team parallelism**: once Phase 2 checkpoints, three developers can take US1 (MVP), US3 (demo mode), and US4 (hosted) concurrently.

---

## Parallel Example: User Story 1 MVP

```bash
# Integration tests (run first, expect to fail):
Task: "Contract test PRD grounding in tests/integration/test_step_1_postgresql.py" (T030)
Task: "Contract test FK graph in tests/integration/test_step_2_fk_graph.py" (T031)
Task: "Contract test live sample in tests/integration/test_step_3_sample.py" (T032)
Task: "Contract test zip delivery in tests/integration/test_step_4_zip.py" (T033)
Task: "Contract test keepalive timeout in tests/integration/test_keepalive_timeout.py" (T034)

# Frontend step handlers (run in parallel once T026 shell is ready):
Task: "Step 1 PRD renderer in frontend/src/hooks/useAgent.ts" (T041)
Task: "Step 2 ERD renderer in frontend/src/hooks/useAgent.ts" (T042)   # serialize if same file
Task: "Step 3 logical model renderer in frontend/src/hooks/useAgent.ts" (T043)   # serialize if same file
```

Note: T041–T043 mutate the same file; while logically independent, run sequentially or split into separate hook modules.

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup.
2. Complete Phase 2: Foundational (**CRITICAL** — blocks every story).
3. Complete Phase 3: User Story 1.
4. **Stop and validate**: quickstart.md steps 1–6 against Northwinds.
5. **Demo to stakeholders**: this is already a usable product.

### Incremental Delivery

1. Setup + Foundational → Foundation ready.
2. US1 → validate → **ship MVP**.
3. US2 → validate → ship multi-source.
4. US3 → validate → ship demo-mode safety net.
5. US4 → validate → ship hosted access.
6. US5 regression → validate → preserve Streamlit + CLI.
7. Phase 8 Polish → constitution gates pass → merge branch.

### Parallel Team Strategy

After Phase 2 checkpoint:
- Developer A: US1 (P1, MVP backbone) — highest priority path.
- Developer B: US3 (P3, entirely frontend — no backend coupling) can start immediately.
- Developer C: US4 (P3, deployment wiring) can start immediately but must pull from A's branch before integration smoke.
- US2 waits for US1 to demonstrate source-switching works for one driver.
- US5 regression runs last, once all other stories have integrated.

---

## Notes

- Every task has an absolute file path — no discovery required.
- `[P]` = distinct files and no dependencies on incomplete tasks.
- User-story checkpoints are hard stops: validate the story independently before moving on.
- ADR-015 gets any new decisions in-flight (Addendum E, Constitution v2.2.0) — do not defer.
- Every task commit should reference its ID (e.g., `T030: contract test for PRD grounding`) for audit.
- `/speckit.analyze` is recommended after this file lands but before `/speckit.implement` to catch cross-artifact drift.
