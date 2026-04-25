# Feature Specification: DSA Frontend × PlatformAgent Backend Integration

**Feature Branch**: `001-dsa-agent-integration`
**Created**: 2026-04-17
**Status**: Draft
**Input**: User description: "Combine the DSA MVP frontend with the PlatformAgent backend so the polished 4-step data product workflow (requirements → conceptual model → logical model → detailed spec) is driven by PlatformAgent's real AI agents and database tools instead of pre-scripted responses."

## Clarifications

### Session 2026-04-17

- Q: What concurrent-user scale is the integration targeting? → A: Small team — up to 10 concurrent phData users (internal demos and evaluation).
- Q: How are generated dbt project + semantic layer artifacts delivered to the user in deployed mode? → A: Browser zip download — response streams a zip; no server-side persistence; no new Terraform modules required.
- Q: How are database credentials handled across sessions? → A: Session-only always — no persistence, no opt-in. Users re-enter credentials (or re-SSO) each session.
- Q: How is a session identified for memory/isolation purposes? → A: Per-tab session ID stored in browser sessionStorage — survives refresh within that tab, does not survive tab close, new tab mints a new session ID. AgentCore Memory records are keyed on this ID.
- Q: What timeout strategy applies to long-running agent operations (schema scan, dbt generation)? → A: Keepalive-driven over the existing SSE stream — unlimited duration while progress events flow; 30 seconds of stream silence is treated as a failure; a cancel button is always available to the user.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Live demo with real customer database (Priority: P1)

A phData solution architect opens the combined application, connects to a customer's PostgreSQL database, and walks the customer through the 4-step data product workflow. At each step, the UI presents information grounded in the customer's actual schema and data rather than canned examples. By the end of the session the customer sees a proposed data product with real table names, real column types, real relationships, and a generated dbt project scaffolded from their own database.

**Why this priority**: This is the core business value — it is the reason the two repos are being combined. Without it, the combined product offers nothing beyond what either repo already provides. Every other story is a refinement of this one.

**Independent Test**: Launch the app locally, connect to the Northwinds PostgreSQL database seeded by `scripts/bootstrap.sh`, walk through all four steps, and verify that each step surfaces information derived from Northwinds (e.g., the `orders`, `customers`, `products` tables) rather than pre-scripted placeholders. At the end, verify a dbt project has been generated targeting Northwinds tables.

**Acceptance Scenarios**:

1. **Given** the combined application is running locally and Northwinds has been seeded, **When** the user provides PostgreSQL connection details in the UI and proceeds to Step 1, **Then** the Step 1 artifact panel (PRD) lists the real tables and entity counts discovered in Northwinds (14 tables, ~830 orders), and the chat explains the PRD in terms grounded in the observed schema.
2. **Given** the user has completed Step 1 against Northwinds, **When** they advance to Step 2 (conceptual model), **Then** the ERD shows entities and relationships derived from Northwinds' actual foreign keys (e.g., Orders → Customers, Order Details → Orders + Products), not a generic example.
3. **Given** the user has completed Steps 1 and 2, **When** they advance to Step 3 (logical model), **Then** each field in the logical model shows the real data type, nullability, and a small sample of values pulled live from Northwinds.
4. **Given** the user has completed Steps 1–3, **When** they advance to Step 4 (detailed requirements) and approve the final gate, **Then** a dbt project is generated on disk that references the real Northwinds tables, compiles cleanly with `dbt compile`, and includes a semantic layer YAML file referencing the logical model's measures.

---

### User Story 2 — Multi-source support: Snowflake and Redshift (Priority: P2)

The same end-to-end workflow from User Story 1 works against Snowflake (Pinnacle Financial demo database, SSO auth) and Redshift (bootstrapped Northwinds replica) without code changes, so the solution architect can demonstrate against whichever data platform the customer uses.

**Why this priority**: Single-database support proves the integration, but phData's customers run a mix of Snowflake and Redshift. Multi-source coverage is what makes the combined product demo-ready across the customer base rather than only for PostgreSQL customers.

**Independent Test**: Repeat the User Story 1 flow once against the Pinnacle Financial Snowflake database (9 tables, 5 dims + 4 facts) using SSO/externalbrowser auth, and once against the bootstrapped Redshift Northwinds. Verify that each run produces a working dbt project scaffolded for the respective adapter (dbt-snowflake, dbt-redshift).

**Acceptance Scenarios**:

1. **Given** the user selects "Snowflake" as the source type, **When** they provide account, role, warehouse, database, schema, and initiate SSO, **Then** an external browser opens for Okta/SAML login, the app receives the session, and Step 1 proceeds with the Pinnacle Financial schema.
2. **Given** the user selects "Redshift", **When** they provide workgroup/host connection details, **Then** Step 1 through Step 4 complete successfully and produce a Redshift-targeted dbt project.
3. **Given** any of the three supported source types has been used end-to-end, **When** the user starts a new session and picks a different source type, **Then** no state from the prior source leaks into the new session's artifacts.

---

### User Story 3 — Offline demo without live database (Priority: P3)

A phData presenter in an environment without database connectivity (conference WiFi, customer site with locked-down network) can still run a polished end-to-end walkthrough using pre-scripted content, preserving the UX experience when real backend calls are not available.

**Why this priority**: Demos fail often due to network issues. A graceful fallback is important for conference and customer-site demos but is not blocking the core value proposition of the product.

**Independent Test**: Launch the app with the backend deliberately unreachable (or with a "demo mode" toggle enabled). Walk through all four steps and verify that pre-scripted responses appear, all artifacts populate with placeholder content from the bundled mock datasets (Atlan, Snowflake, Highspot, data-products), and the experience is visually indistinguishable from a real run.

**Acceptance Scenarios**:

1. **Given** demo mode is enabled by the user via a visible toggle, **When** they complete all four steps, **Then** every step's chat and artifact panels populate from pre-scripted content, and no backend calls are attempted.
2. **Given** demo mode is disabled, **When** the backend call for any step fails (timeout, network error, auth failure), **Then** the user sees a clear error message and is offered the option to continue that step in demo mode.
3. **Given** the user is in demo mode, **When** they look at any artifact panel, **Then** a visual indicator clearly marks the content as "demo" so it cannot be mistaken for real customer data.

---

### User Story 4 — Multi-user deployed access (Priority: P3)

A phData team member accesses the combined application at a hosted URL (existing Amplify deployment) using their phData SSO credentials, so that multiple teammates (up to roughly ten concurrent) can demo and evaluate the product without each provisioning their own local stack.

**Why this priority**: Shared hosted access is important for team adoption and iteration but is not required to prove the core integration. Local Docker Compose already provides an adequate developer experience.

**Independent Test**: From a fresh browser, visit the Amplify-hosted URL, authenticate via Cognito PKCE against the existing user pool, and complete the User Story 1 workflow end-to-end against Northwinds (or whatever RDS instance is currently attached to the deployment).

**Acceptance Scenarios**:

1. **Given** an authorized phData user visits the hosted URL, **When** they click sign-in, **Then** Cognito's hosted UI presents, SSO completes, and they are returned to the app authenticated.
2. **Given** an authenticated user initiates the 4-step workflow, **When** an agent call is made, **Then** the request reaches the AgentCore Runtime via the Gateway with valid JWT and the agent responds within the same user experience as local mode.
3. **Given** up to ten authenticated users are using the app concurrently from different browsers, **When** each completes a workflow, **Then** neither user's database connections, generated artifacts, nor conversation history are visible to the others, and all workflows complete within the success-criteria latency targets.

---

### User Story 5 — Existing alternative interfaces remain usable (Priority: P4)

The Streamlit "Talk to Your Data" app and the Python CLI (`uv run python -m platform_agent`) continue to work unchanged so existing internal workflows and scripted demos are not broken by the integration.

**Why this priority**: These are secondary surfaces used by the team for quick investigations. They must not regress, but they are not where the new business value lives.

**Independent Test**: After the integration lands, run `uv run streamlit run streamlit_app/app.py` and `uv run python -m platform_agent` and verify both launch, connect to PostgreSQL/Redshift/Snowflake, and answer at least one schema question end-to-end.

**Acceptance Scenarios**:

1. **Given** the integration has been merged, **When** Streamlit is launched, **Then** it connects to a selected database type, scans the schema, and answers a natural-language question using the same agent tools as before.
2. **Given** the integration has been merged, **When** the CLI is launched, **Then** it accepts a user question and returns an agent response using the same agent-factory configuration as before.

---

### Edge Cases

- **Backend reachable but unauthenticated (deployed mode)**: User sees a sign-in prompt before any workflow step starts; partial state is not silently dropped.
- **Database connection succeeds but schema scan returns zero tables**: User sees a clear "schema is empty" message and is given the option to pick a different schema or switch to demo mode, rather than a workflow that proceeds with empty artifacts.
- **Schema scan takes longer than expected (large warehouse)**: Progress is visible in the UI (streaming updates, elapsed time); user can cancel and still see a partial result if any tables have been discovered.
- **Agent call exceeds model context window**: The system truncates or summarizes the supplied schema context gracefully rather than surfacing a raw model error; user sees an explanatory message.
- **User switches source database mid-session**: Prior artifacts are either discarded with confirmation or preserved as read-only history; state never silently mixes two sources.
- **User refreshes the browser mid-workflow**: Conversation history and gate decisions survive the refresh (backed by existing conversation-memory facility); if memory is unavailable, the user is warned and can choose to restart or proceed ephemerally.
- **dbt project generation writes files that conflict with an existing output directory**: User is asked whether to overwrite, timestamp a new directory, or cancel — files are never silently overwritten.
- **Demo-mode content is shown while a real connection is active**: The visual "demo" indicator is always present in demo mode and the UI prevents a user from believing demo output is real.
- **Cognito session expires mid-workflow**: User is prompted to re-authenticate; in-flight artifacts are preserved where possible.
- **Concurrent workflows in two browser tabs by the same user**: Each tab has an independent session; neither silently overwrites the other's state.

## Requirements *(mandatory)*

### Functional Requirements

#### Repository Structure & Preservation

- **FR-001**: The combined repository MUST retain the DSA frontend's complete 4-step user experience, including its step/gate structure, theme system (Sana, phData, Dark, Minimal presets), ERD visualization, artifact panels, and chat/suggested-reply UI.
- **FR-002**: The combined repository MUST retain every PlatformAgent backend capability currently on the main and snow-iceberg-migration branches, including the Strands agent factory, Bedrock model configuration, database driver abstraction layer (PostgreSQL, Redshift, Snowflake), and the current tool suite (connect, scan, profile, query, DDL, dbt-generate, semantic-layer).
- **FR-003**: The combined repository MUST preserve the Streamlit "Talk to Your Data" app and the Python CLI as functional alternative interfaces without behavioral regression.
- **FR-004**: The combined repository MUST preserve the multi-agent snow-iceberg patterns (migration, enrichment, quality, mapping, query) for future use, even if the initial integration wires only the single-agent pattern into the DSA UI.

#### Workflow Step Behavior

- **FR-005**: At Step 1 (Requirements / PRD), the system MUST allow the user to establish a live connection to a supported source database and discover its schema before drafting the PRD; the drafted PRD MUST reference entities, tables, and domains observed in the connected source rather than generic placeholders.
- **FR-006**: At Step 2 (Conceptual Model), the system MUST propose entities and relationships derived from the actual foreign-key graph and naming conventions of the connected database, rendered in the existing ERD visualization.
- **FR-007**: At Step 3 (Logical Model), the system MUST sample the real data of each proposed field and populate data types, nullability, and representative values from live query results rather than invented values.
- **FR-008**: At Step 4 (Detailed Requirements), the system MUST produce a dbt project and semantic layer that target the connected source's adapter (dbt-postgres, dbt-redshift, or dbt-snowflake) and reference the real tables/columns identified in earlier steps. In local developer mode the artifacts MUST be written to the local filesystem (`dbt_output/<project>/`). In deployed mode the artifacts MUST be packaged as a single zip and delivered to the user via a browser download initiated from the Step 4 UI; the server MUST NOT persist generated artifacts beyond the life of the request.
- **FR-009**: Each step MUST preserve the existing gate-approval mechanism — the user must explicitly approve advancement — and MUST record gate decisions in a way that survives a browser refresh.
- **FR-010**: The system MUST allow the user to re-run any prior step within the same session (for example, to re-scan the schema if tables were added) without losing decisions already approved at subsequent gates unless the user explicitly accepts invalidating them.

#### Source Database Support

- **FR-011**: The system MUST support PostgreSQL, Redshift, and Snowflake as source databases selectable from the UI at session start.
- **FR-012**: When the user selects Snowflake, the system MUST support SSO authentication via an external-browser redirect flow in addition to any password-based mode.
- **FR-013**: The system MUST display connection status (not connected / connecting / connected / failed) in a persistent location in the UI throughout the session.
- **FR-014**: The system MUST NOT persist database credentials beyond the active session under any circumstances. No opt-in storage mechanism is offered in this release: credentials live only in the active browser session's memory and are discarded on session end. Snowflake users rely on SSO/externalbrowser (no password typed); PostgreSQL/Redshift users retype credentials per session.

#### Demo Mode

- **FR-015**: The system MUST provide a user-visible toggle or mode indicator that switches between "live" (real backend/database) and "demo" (pre-scripted) behavior.
- **FR-016**: When demo mode is active, the system MUST NOT issue any backend agent calls and MUST populate artifacts from bundled mock datasets.
- **FR-017**: When a backend call fails in live mode, the system MUST give the user an option to continue that step in demo mode, rather than blocking the workflow.
- **FR-018**: All demo-mode artifacts MUST carry a clear visual indicator so the user cannot mistake them for real customer data.

#### Deployment & Access

- **FR-019**: The combined application MUST deploy to the existing AWS infrastructure (AgentCore Runtime, Gateway, Memory, Cognito User Pool, Amplify hosting) without requiring new Terraform modules to be created, although existing modules may be updated.
- **FR-020**: The combined application MUST authenticate hosted users via the existing Cognito User Pool with PKCE browser flow and MUST authorize agent calls via the existing Gateway OAuth2 machine-to-machine credential path.
- **FR-021**: The combined application MUST run locally against a developer's machine with a single command (Docker Compose), requiring no deployed AWS resources beyond what a developer can bootstrap with `scripts/bootstrap.sh`.
- **FR-022**: A successful deployment MUST NOT require downtime of existing PlatformAgent functionality — existing Runtime, Gateway, and Memory resources MUST continue to serve requests during and after deployment.

#### Observability & Feedback

- **FR-023**: The system MUST surface agent progress to the user incrementally during long-running calls (schema scans, dbt generation) rather than freezing the UI with no feedback. Progress events MUST be emitted by the backend at least every 30 seconds while an operation is in progress; 30 seconds of silence on the progress stream MUST be treated by the frontend as a failure. The frontend MUST always expose a cancel control for in-progress operations.
- **FR-024**: The system MUST log agent traces via existing observability wiring (OpenTelemetry → CloudWatch) so that any failed workflow step can be diagnosed after the fact.
- **FR-025**: The system MUST expose errors in a human-readable form at the point of failure (which step, which tool, what the underlying error was), not as a generic "something went wrong."

#### Data Isolation & Session Integrity

- **FR-026**: The deployed application MUST support up to ten concurrent authenticated phData users without session-state cross-contamination: no user's connection details, chat history, or generated artifacts may be visible to another.
- **FR-027**: A single user's concurrent browser sessions (e.g., two tabs) MUST each have independent state; each tab MUST mint its own session identifier, stored in the browser's per-tab session storage so that a refresh preserves that tab's state but a new tab always starts a fresh session. One tab MUST NOT silently overwrite another's artifacts.
- **FR-028**: When a user switches source database mid-session, the system MUST either clearly discard prior artifacts with user confirmation or preserve them as read-only history — never silently mix artifacts from two sources.

#### Conversation Continuity

- **FR-029**: A user's workflow state (gate decisions, current step, generated artifacts, chat history) MUST survive a browser refresh within the same browser tab when the backend's conversation memory facility is reachable; the session identifier kept in per-tab session storage MUST be used to look up the persisted conversation and state. Closing the tab ends the session; reopening does not resume.
- **FR-030**: When the memory facility is unreachable, the user MUST be warned before proceeding rather than silently losing continuity.

### Key Entities

- **Source Database Connection**: A user-supplied handle to an external PostgreSQL, Redshift, or Snowflake database. Holds host/account, credentials, source type, schema, and current status. Scope: strictly single-session — credentials and connection handles are discarded when the session ends; no persistence path exists.
- **Discovered Schema**: The structural metadata extracted from a Source Database Connection — tables, columns, data types, primary and foreign keys, row counts, sample values. Scope: single session.
- **Data Product Specification**: The evolving user-facing artifact across all four steps — PRD (step 1), Conceptual Model/ERD (step 2), Logical Model (step 3), Detailed Requirements + dbt project + semantic layer (step 4). Scope: single session, with gate decisions recorded alongside.
- **Gate Decision**: An explicit user approval (or rejection) at each step boundary; persists across browser refresh within a session.
- **Workflow Step State**: Which step the user is currently on, which prior steps are completed, and which are invalidated by a re-run.
- **Demo Mode Flag**: A per-session toggle that switches all four steps between live-backend and pre-scripted behavior.
- **Agent Conversation**: The ongoing dialogue between the user and the backend agent, persisted by the existing memory facility so that a browser refresh does not lose history.
- **Generated Artifact File**: Files produced at Step 4 (dbt project, semantic layer YAML). Scope: written to local filesystem in developer mode; packaged as an in-memory zip and streamed to the browser for direct download in deployed mode. Deployed-mode artifacts are ephemeral — the server does not persist them after delivery.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A phData solution architect can complete the full 4-step workflow against a real Northwinds PostgreSQL connection in under 15 minutes end-to-end, including schema discovery and dbt generation.
- **SC-002**: In at least 80% of fresh sessions against a healthy database, the user completes all four steps without needing to retry any step due to a backend or agent failure.
- **SC-003**: 100% of generated dbt projects compile successfully on first attempt (`dbt compile` exits 0) against the source they were generated for.
- **SC-004**: Schema-grounded content (real table and column names from the connected database) appears in the Step 1 artifact panel within 30 seconds of the user confirming their database connection, under normal network conditions.
- **SC-005**: All three supported source types (PostgreSQL, Redshift, Snowflake) complete the 4-step workflow end-to-end without code changes between runs — only UI-level source selection differs.
- **SC-006**: The Streamlit and CLI interfaces continue to function without regression; 100% of their pre-integration acceptance flows still pass after the integration lands.
- **SC-007**: No existing AWS-deployed resource is re-provisioned during the integration rollout; the existing Runtime, Gateway, Memory, Cognito User Pool, and Amplify app continue serving requests throughout the rollout.
- **SC-008**: Demo-mode walkthrough completes all four steps with zero backend calls and zero network dependencies.
- **SC-009**: A failed agent call surfaces a specific, actionable error message to the user within 5 seconds of failure detection, rather than an indefinite spinner or a generic "something went wrong."
- **SC-010**: Ten concurrent authenticated users of the hosted deployment can each complete independent workflows without observable cross-contamination of state, and without any user's end-to-end workflow latency exceeding the single-user targets by more than 25%.
- **SC-011**: A browser refresh during any of the four steps restores the user's state (current step, gate decisions, partial artifacts) in more than 95% of refresh events when memory is healthy.
- **SC-012**: The combined repository is self-contained: a newcomer can clone it, run `scripts/bootstrap.sh` and `docker-compose up`, and reach the first workflow step in under 20 minutes with no further documentation lookup.

## Assumptions

- **Target users**: Primary users are phData solution architects and data engineers using the tool for live customer demos and discovery sessions. Secondary users are internal phData engineers evaluating or iterating on the product. The tool is not currently intended for direct customer self-service.
- **Scope**: The initial integration wires only the single-agent PlatformAgent pattern (from main branch) into the DSA 4-step UX. The five-agent migration pattern (snow-iceberg-migration) is preserved in the repository but is not surfaced into the DSA UI in this feature; it remains accessible via the existing agent selector or alternative interfaces.
- **Deployment target**: The existing AWS account, region, Cognito User Pool, Amplify app, AgentCore Runtime/Gateway/Memory, RDS, and Redshift Serverless resources are the deployment target. This feature does not provision a new stack.
- **Source databases available for demos**: The bootstrapped Northwinds (PostgreSQL + Redshift) and the Pinnacle Financial Snowflake demo cover the supported source types.
- **Authentication**: Hosted access uses the existing Cognito User Pool and its current user list. No user-management work is in scope.
- **Credential handling**: Database credentials entered by the user are strictly session-scoped. No persistence layer (localStorage, Secrets Manager, or otherwise) is provided in this release.
- **Conversation memory**: The existing AgentCore Memory facility (30-day retention) provides refresh-survivable state. This feature does not alter retention.
- **Frontend source**: The DSA frontend is imported from the `feat-enhancements-erd-visuals` branch (simpler useAgent, removed OpenQuestionsView, simplified ConceptualERD) rather than DSA's main branch.
- **Demo mode scope**: Pre-scripted content reuses the bundled mock datasets (Atlan, Snowflake, Highspot, data-products) that already ship with the DSA frontend.
- **Error handling**: Long-running operations use keepalive-driven timeouts over the existing SSE channel — as long as the backend emits progress events (at least every 30 seconds), the operation continues; 30 seconds of stream silence is treated as a failure. Transient failures (network blips, auth refresh) retry once with exponential backoff; a second failure surfaces a user-facing error and offers demo-mode continuation.
- **Mobile support**: Out of scope for this feature. Desktop browsers only.
- **Internationalization**: Out of scope. English-only UI.
- **Constitution compliance**: Any new backend code follows the existing driver/tool/observability conventions already defined in the repository. Frontend code follows the DSA project's TypeScript conventions.

---

## Addendum — Talk-to-Data (2026-04-24 scope add)

### Clarifications

- **Q (2026-04-24, post-plan scope add)**: Should an ad-hoc NL→SQL surface be included in this release?
- **A**: Yes — "Talk to Data" tab on the artifact panel, available once a source connection exists and the Step 1 PRD has been drafted. SELECT-only, 250-row cap, direct Bedrock call (not full agent loop). See ADR-015 D17.

### Functional Requirements (ad-hoc querying)

- **FR-031**: After a source connection is established and the Step 1 PRD has been drafted, the UI MUST expose a "Talk to Data" tab on the artifact panel that accepts a plain-English question and returns a live query result against the connected source.
- **FR-032**: The system MUST translate the user's question to SQL via an LLM grounded in the real scanned schema (tables + columns) so the generated SQL references only columns that exist in the source.
- **FR-033**: The system MUST enforce read-only execution: only SELECT / WITH statements are allowed; any DDL/DML keyword (INSERT, UPDATE, DELETE, DROP, TRUNCATE, ALTER, CREATE, GRANT, REVOKE, MERGE, REPLACE, CALL, EXECUTE, COPY) MUST result in a rejected request before execution.
- **FR-034**: The system MUST enforce a server-side row cap (250 rows) regardless of the LLM's generated SQL, surfacing a "truncated" indicator when exceeded.
- **FR-035**: The UI MUST display both the generated SQL (for trust/traceability) and the resulting rows in a sortable/selectable table so users can verify the translation and inspect the data simultaneously.
