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

## Amendments

Decisions landing in later `/speckit.clarify` answers, `/speckit.plan`, or implementation will be appended here with a date stamp.
