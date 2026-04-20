# ADR-015: DSA Frontend × PlatformAgent Backend Integration

**Status**: Proposed (in-flight during `/speckit.clarify`, will move to Accepted after `/speckit.plan`)

**Date**: 2026-04-17

## Context

Two repositories — DSA MVP (polished React 4-step data-product workflow with pre-scripted agent flows) and PlatformAgent (Python/Strands agent backend with real database drivers, dbt generation, and deployed AgentCore infrastructure) — are being combined into a single `dsa-platform` repository so the polished UX is driven by real AI agents instead of pre-scripted responses.

This ADR captures decisions made during the specification and clarification phases for feature `001-dsa-agent-integration`. Per constitution v2.2.0 Addendum E, this ADR is authored in-flight and amended with each new decision as it lands.

## Decisions

### D1 — Repo combination strategy

**Decision**: Combine into a new `dsa-platform` repo. PlatformAgent branches (`main` + `snow-iceberg-migration`) merged as base; DSA frontend imported from `feat-enhancements-erd-visuals` branch into `frontend/`, replacing PlatformAgent's basic React scaffold.

**Rationale**: Preserves full AgentCore deployment (Runtime/Gateway/Memory/Cognito/Amplify) and the five-agent snow-iceberg work while adopting DSA's polished UX. The `feat-enhancements-erd-visuals` branch is chosen over DSA main because it simplifies `useAgent.ts` from ~1000 to ~300 lines and cleans up the ERD before we rewrite it anyway — avoids importing code we would immediately delete.

### D2 — UX framework preserved; backend wiring rewritten

**Decision**: DSA's step/gate structure, theme system (Sana, phData, Dark, Minimal), ERD, and artifact panels are preserved verbatim. DSA's `claude.ts` is replaced by PlatformAgent's `agentcore-client` SSE streaming module. `useAgent.ts` is rewritten to call PlatformAgent tools at each step instead of pre-scripted flows.

**Rationale**: The 4-step UX is the business value DSA brings; the agent backend is the business value PlatformAgent brings. Each side keeps what it is best at.

### D3 — Concurrent-user target (from `/speckit.clarify` Q1)

**Decision**: Target scale is up to 10 concurrent phData users (small internal team). Not sized for department or customer-facing production.

**Rationale**: Honest near-term target — internal demos and evaluation. Larger scale would require formal load testing that the clarify answer deferred as out of scope.

**Implications**:
- Existing AgentCore Runtime sizing is sufficient; no additional autoscaling work required.
- Data-isolation requirements (FR-026, FR-027) still apply at this scale.
- Conversation Memory partitioning stays on per-user keys (existing pattern).

### D4 — Deployed-mode dbt artifact delivery (from `/speckit.clarify` Q2)

**Decision**: In deployed mode, Step 4 artifacts (dbt project + semantic layer) are packaged in-memory as a zip and streamed to the browser for direct download. No server-side persistence. No new Terraform modules (no S3 bucket for artifacts, no RDS table, no DynamoDB). Local developer mode continues to write to `dbt_output/<project>/` on disk.

**Rationale**:
- Simplest path that honors FR-019 ("no new Terraform modules required").
- Matches the demo-tool context — the user runs `dbt compile` locally with the downloaded artifact.
- Sidesteps retention/privacy questions (no customer schema/data at rest in our infrastructure).
- Avoids pre-signed URL lifecycle complexity, bucket policies, and S3 CORS setup.

**Rejected alternatives**:
- S3 + pre-signed URL: would add a Terraform module, retention policy, and CORS; unnecessary at small-team scale.
- Direct push to a customer git repo: couples to per-customer git configuration; out of scope for this release.
- Both zip + S3: doubles surface area for negligible benefit.

**Implications**:
- Backend `agent.py`/`serve.py` or a thin FastAPI wrapper must produce a zip response at Step 4 rather than writing files.
- Frontend Step 4 must trigger a browser download from the agent response stream.
- Size budget: dbt projects for demo databases are small (<2 MB zipped); well within HTTP response limits.

## Consequences

**Positive**:
- Minimal new infrastructure — every existing AWS resource continues serving traffic unchanged.
- Clear separation between developer mode (filesystem) and deployed mode (download), both easily testable.
- Low risk of regressing the five-agent snow-iceberg work or the Streamlit/CLI interfaces — this integration only adds a new frontend entry point.

**Negative**:
- Download-only delivery means a user cannot revisit an old generated project from the hosted deployment (local mode retains files).
- Small-team scale target means we will need to revisit sizing if we decide to open the tool to customers.
- Frontend download-triggering adds a streaming response format that the existing `agentcore-client` SSE parsers must accommodate.

### D5 — Database credential persistence (from `/speckit.clarify` Q3)

**Decision**: Database credentials are strictly session-scoped. No opt-in storage is offered in this release. Users re-enter or re-SSO per session. Snowflake's externalbrowser authenticator handles the repetitive-login concern for SSO-backed sources.

**Rationale**:
- Minimum security surface: no credential-storage path means no credential-exfiltration path.
- Zero new infrastructure: no Secrets Manager entries, no browser-side encryption keys, no revocation flow.
- Matches demo-tool context — architects bring fresh credentials per session or use SSO.
- Consistent with FR-019 (no new Terraform modules) and with the zip-download decision (D4): the hosted deployment stores nothing customer-specific at rest.

**Rejected alternatives**:
- Browser localStorage opt-in: would require XSS-resistant encryption, clear revocation UX, and per-device inconsistency; complexity exceeds benefit at small-team scale.
- Secrets Manager keyed on Cognito user: couples session lifecycle to AWS identity management, adds a Terraform module, and creates a customer-credential retention obligation.
- Mode-dependent behavior (session-only deployed, localStorage in dev): inconsistent security posture across modes; not worth the UX savings.

**Implications**:
- Connection sidebar UX is unambiguous: always "connect fresh" path, no "saved connections" list to maintain.
- Post-release, if users demand credential persistence, localStorage opt-in is the logical next step — not AWS-side storage.

### D6 — Session scoping for memory and isolation (from `/speckit.clarify` Q4)

**Decision**: Each browser tab mints its own UUID session identifier on first load and stores it in `sessionStorage`. AgentCore Memory records and all per-session state in the UI are keyed on this identifier. A refresh preserves the identifier (sessionStorage survives reload). Closing the tab discards the identifier; a newly opened tab creates a new one.

**Rationale**:
- Only design that satisfies both FR-027 (tabs isolated) and FR-029 (refresh-survivable state) without contradiction.
- `sessionStorage` is the standard browser primitive for exactly this scope; no custom lifecycle code required.
- Matches demo-tool usage: sessions are short-lived, scoped to a single demo conversation; historical replay is not a user need in this release.
- AgentCore Memory's 30-day retention becomes a natural garbage-collection boundary rather than the session boundary.

**Rejected alternatives**:
- Per-user session in localStorage: shared across tabs, violates FR-027, and creates a messy concurrent-tab state problem.
- Explicit "resume session" picker: adds significant UX and a session-list data model for a feature users in this scale tier are unlikely to use.
- Per data-product-spec identifier: conflates the durable artifact (the spec) with the ephemeral identifier (the session); would require users to name a spec up front.

**Implications**:
- Session-ID provisioning happens in `AppContext` on mount if sessionStorage is empty.
- Backend receives the session ID as a header/context param on every agent call and uses it as the memory key.
- The "start new session" UX (if offered) is simply "open a new tab" — no special UI needed.
- Privacy: closing the tab is effectively a session logout from the conversation perspective; no stale state lingers on the client.

### D7 — Long-running operation timeout strategy (from `/speckit.clarify` Q5)

**Decision**: Agent operations use a keepalive-driven timeout over the existing SSE stream. The backend MUST emit at least one progress event every 30 seconds during any long-running operation (schema scan, data sample, dbt generation). As long as events flow, the operation continues indefinitely. 30 seconds of stream silence is treated as a failure by the frontend. A cancel button is always available to the user and cleanly aborts the operation.

**Rationale**:
- Matches the SSE architecture already shipped in `agentcore-client` — no new transport required.
- Avoids false failures on slow warehouses (Snowflake cold-start, cross-region queries) while still catching genuine stalls in under a minute.
- Per-operation budgets (Option B) are plausible but brittle — they hard-code assumptions about acceptable duration that will drift as databases and dbt projects evolve.
- No-timeout (Option C) leaves users staring at indefinite spinners when the backend silently hangs; keepalive + cancel is the honest middle ground.
- The cancel button also serves the edge-case of the user realizing they connected to the wrong database mid-operation.

**Rejected alternatives**:
- Hard 60s timeout (A): causes false failures on legitimate operations against real warehouses.
- Per-operation budgets (B): rigid, high-maintenance, and assumes we know every operation class up front.
- No server-side timeout (C): no stall detection; bad UX when backend silently hangs.

**Implications**:
- Backend agent tools MUST be wrapped (or the agent loop MUST be instrumented) to emit heartbeat events at ≤ 30s intervals even during long single tool calls.
- Frontend SSE handler adds a silence-timer reset on every event and a 30s timeout alarm.
- Existing OTel traces (per Addendum E) provide post-hoc visibility into which tool calls exceed typical durations.

### D8 — Backend entry shape: FastAPI sidecar over Strands (from `/speckit.plan` research R1)

**Decision**: Introduce `src/platform_agent/api/` as a thin FastAPI app that owns HTTP routing, SSE streaming, session-ID extraction, and zip response generation. The Strands agent factory is invoked in-process. The legacy `serve.py` AG-UI adapter remains untouched for existing integrations.

**Rationale**: Control over SSE event schema, first-class support for streamed zip responses, and predictable keepalive emission from an async generator. Keeps the container count at one (no new Terraform module).

**Rejected alternatives**: reuse the AG-UI adapter (custom events don't fit), new `BedrockAgentCoreApp` pattern (duplicates existing wiring), Lambda + API Gateway (cold start + new module).

### D9 — Dual-layer keepalive heartbeats (from `/speckit.plan` research R2)

**Decision**: A passive SSE emitter sends a `heartbeat` event every 10 seconds of idle, plus long-running `@tool` functions emit `tool_progress` events at natural boundaries (per-table, per-column, per-model). The frontend's 30-second silence timer resets on any event of either type.

**Rationale**: Two layers cover two failure modes — a stuck tool still emits passive heartbeats; a live tool emits meaningful progress. Three heartbeats fit in the 30-second window, surviving a lost packet.

### D10 — Two-phase zip delivery for Step 4 (from `/speckit.plan` research R3)

**Decision**: Phase 1 — agent produces the project and emits an `artifact_ready` SSE event carrying a UUID handle (60-second TTL, single-use). Phase 2 — frontend issues `GET /workflow/artifact/{handle}` and receives a streamed zip. Handle store lives in `app.state` guarded by `asyncio.Lock`; sweep task drops expired entries every 60 seconds.

**Rationale**: SSE cannot carry binary cleanly; a second HTTP request with `StreamingResponse` is the standard approach. Short TTL + single-use + session-ID binding prevents replay or inter-user leakage.

**Rejected alternatives**: base64-in-SSE (33% bloat, awkward reconstruction), WebSocket channel (new protocol, Gateway upgrade untested), JSON inline (loses browser download UX).

### D11 — Session-ID via `X-DSA-Session-ID` header; Memory key derivation (from `/speckit.plan` research R4)

**Decision**: Frontend mints a UUIDv4 on first mount, stores in `sessionStorage`, and sends it on every request via the custom header `X-DSA-Session-ID`. Backend derives the AgentCore Memory key as `dsa:{cognito_sub or "local"}:{session_id}` — the user-scope prefix provides defense-in-depth against astronomically unlikely UUID collisions across identities.

**Rationale**: Headers survive CORS preflight cleanly and don't leak into referer/query logs. User-scope prefix makes CloudWatch log filtering by user trivial and makes cross-identity collisions harmless by construction.

**Rejected alternatives**: JWT custom claim (mutation complicates Cognito), query string (log leakage), request body (SSE endpoints want GET-style streaming).

### D12 — Step-scoped prompts + tool allowlist (from `/speckit.plan` research R6)

**Decision**: Each of the four DSA steps has its own system-prompt Markdown file under `src/platform_agent/prompts/steps/` and its own `StepConfig` entry declaring `allowed_tools`. The factory loads the prompt and wraps the Strands agent with a tool filter.

Per-step tool allowlist:
- Requirements: `connect_to_database`, `scan_metadata`
- Conceptual: `scan_metadata`, `run_query` (FK inspection only)
- Logical: `run_query`, `profile_database`
- Detailed: `generate_dbt_project`, `generate_semantic_layer`

**Rationale**: Constitution Article VI requires step-scoped personas and forbids cross-step context bleed. Markdown prompt files satisfy Article IV's "never inline strings." Tool filtering is the structural enforcement of Article VI beyond prompt discipline.

### D13 — Demo mode is frontend-only (from `/speckit.plan` research R7)

**Decision**: Demo mode lives entirely in the React app. `useAgent.ts` short-circuits when `AppContext.demoMode.enabled`, invoking `demoMode.resolveStep()` which synthesises responses from `frontend/src/data/mock/`. The backend never knows demo mode exists. Every demo-mode artifact renders a persistent `<DemoBadge>` (FR-018).

**Rationale**: Demo mode must survive when the backend is unreachable — that's its entire purpose. Any backend coupling compromises that. Frontend-only also means no demo traffic in traces or analytics.

**Rejected alternatives**: backend `?mode=demo` flag (dies with backend), separate mock-backend container (doubles the demo surface), banner-only indicator (fails the "cannot be mistaken" bar).

### D14 — SSE event schema v1 (from `/speckit.plan` research R8)

**Decision**: A closed set of event types (`heartbeat`, `tool_start`, `tool_progress`, `tool_result`, `message`, `artifact_update`, `artifact_ready`, `error`, `done`) with a `v: 1` field on every `data` payload. Pydantic models in `src/platform_agent/api/events.py` own the canonical shapes; frontend parsers under `frontend/src/lib/agentcore-client/parsers/` are version-gated. Every stream ends with exactly one terminal event.

**Rationale**: Closed enum keeps frontend parser exhaustive and detects drift at compile time. Version field enables future evolution without breaking deployed clients.

**Rejected alternatives**: free-form JSON (no type safety), OpenAI delta-only (too token-centric), Protocol Buffers (codegen overhead, negligible savings).

### D15 — Cascading gate invalidation UX (from `/speckit.analyze` remediation U1)

**Decision**: When a user re-runs an earlier step that has approved downstream gates, the frontend opens an `InvalidationConfirm` modal listing the steps that will be cleared. Confirming dispatches a single `WORKFLOW_INVALIDATE_DOWNSTREAM` reducer action that clears artifacts, gate decisions, and chat history for every step **after** the re-run step — earlier steps and the re-run step itself are preserved. Cancel aborts the re-run entirely.

**Rationale**:
- Matches FR-010 ("without losing decisions already approved at subsequent gates unless the user explicitly accepts invalidating them").
- Single reducer action keeps state transitions atomic and testable.
- A modal is the correct deliberate-moment affordance per Constitution Article VI ("Human gates are deliberate moments … not toasts or dismissible dialogs"). The invalidation prompt is itself a gate.
- No silent cascading — the user sees which steps will be affected before confirming.

**Rejected alternatives**:
- Auto-invalidate without confirmation: violates FR-010.
- Read-only "history" of invalidated steps: adds state-model complexity and visual noise for a rare flow.
- Per-step individual re-confirmation: multiplies clicks without adding safety.

**Implications for design**:
- `frontend/src/components/gates/InvalidationConfirm.tsx` renders the modal.
- `AppContext` reducer gains `WORKFLOW_INVALIDATE_DOWNSTREAM`.
- Backend is unaware — invalidation is purely a frontend concern because Memory is append-only event-sourced; old events remain but the projection ignores them after the invalidation marker.

### D16 — `memory_unreachable` error contract (from `/speckit.analyze` remediation U3)

**Decision**: When the backend's AgentCore Memory adapter raises `MemoryUnavailable`, the workflow route emits a terminal SSE `ErrorEvent{code: "memory_unreachable", retriable: true, message: "Conversation memory is unavailable; your session will not survive a refresh."}` and closes the stream. The frontend sets `AppContext.memoryStatus = "unreachable"` and renders a persistent banner until the next successful event.

**Rationale**:
- Closes FR-030 explicitly — users are warned, not silently degraded.
- `retriable: true` lets the frontend offer a retry that reconnects to Memory.
- Extending `SSE event schema v1` (D14) with a new `code` value does not break schema compatibility — the frontend's parser already handles unknown codes as generic errors, and this one's presence is additive.

**Rejected alternatives**:
- Let the request fail with 503: loses the opportunity to keep the user on the step; forces re-navigation.
- Silent continuation with ephemeral-only memory: violates FR-030.
- Separate `/health/memory` poll endpoint: adds a second channel for something that only matters when an actual workflow request needs Memory.

**Implications for design**:
- `src/platform_agent/session/memory_adapter.py` defines a typed `MemoryUnavailable` exception.
- Backend's `routes_workflow.py` wraps Memory calls in `try/except MemoryUnavailable` and emits the new error event.
- Frontend `AppContext` gains `memoryStatus` state and `MEMORY_STATUS_SET` action; `ContextBar.tsx` renders the banner.

## Amendments

Decisions landing in later `/speckit.tasks` or implementation will be appended here with a date stamp.
