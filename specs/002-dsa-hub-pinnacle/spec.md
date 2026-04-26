# Feature Specification: DSA Hub — Pinnacle Cross-Source

**Feature Branch**: `002-dsa-hub-pinnacle`
**Created**: 2026-04-26
**Status**: Draft
**Input**: Evolve the DSA Platform from a single-source workflow into a multi-source hub where two Pinnacle warehouses (operational PostgreSQL + analytical Snowflake) are auto-discovered down to their business processes, where the user can launch prebuilt "pilled" PRDs that combine both sources into governed Iceberg data products, and where every step from discovery through provisioning through validation is visualized with live KPIs and an agent DAG.

## Clarifications

### Session 2026-04-26

- Q: What is the ownership/scope of a workspace? → A: Per-tab/session — workspace lives only in the browser session, no server-side persistence beyond cache (matches today's per-tab UUID model). One workspace per browser tab; closing the tab discards the workspace state.
- Q: What identifier scopes the durable, cross-session assets (semantic graph, registered Iceberg catalog, activity log)? → A: Per-connection — each connection owns its own semantic graph and its own catalog; the platform does NOT reconcile entities across connections in v1. Cross-source data products are still produced (provisioning joins data from multiple connections at build time and writes to an Iceberg connection's catalog), but a single business concept that appears in two source connections (e.g., a `clients` dimension in Postgres and a `dim_client` in Snowflake) remains as two separate entities in two separate per-connection graphs. **Future consideration (v2+):** evolve toward a workspace-level or project/firm-level unified graph that reconciles entities across connections — both the workspace-scoped (Q2 option 2) and project/firm-scoped (Q2 option C) approaches are on the roadmap, but explicitly out of scope for this feature.
- Q: How does a workspace get a target Iceberg/Glue catalog connection for provisioning? → A: The user must add an Iceberg/Glue catalog connection as an explicit third connection in the workspace; provisioning is gated on its presence and fails fast with a "Add Iceberg target connection" prompt if absent. For the live Pinnacle demo, the Iceberg/Glue connection MAY be pre-staged in the workspace so the DSA only visibly adds the two source connections (Postgres + Snowflake) during the 8-minute showcase, but the platform itself requires the Iceberg connection to exist before any PRD acceptance can proceed.
- Q: How are PII/PCI/PHI tags enforced in v1? → A: Informational only — the Standards page lists the policy (categories, definitions, expected handling) but the platform does NOT auto-detect candidate PII columns, does NOT surface tag banners in TTYD responses, does NOT log tag touches in the activity log, and does NOT mask or block at any query path in v1. Auto-detect, banners + logging, masking, and blocking are all on the v2+ roadmap; the v1 data model intentionally does not preclude any of them.
- Q: What is the registration behavior when the auto-validation card is partially red? → A: Threshold gate — provisioning registers the Iceberg product as **final and TTYD-queryable** only when ≥ 80% of the PRD's stated business questions pass (the same line named in SC-004). Below threshold, the product is registered in a **provisional** state, NOT exposed to TTYD, and the run remains on the Build page in a "needs re-plan" status; only a successful rerun (whole or per-failed-question) that lifts the pass rate to ≥ 80% promotes the product to final. Threshold value is configurable but defaults to 80%.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Connect both Pinnacle warehouses and see them as one company (Priority: P1)

A Data Solutions Architect (DSA) running a live customer demo opens the platform, lands on a Connections workspace, and adds two sources representing the same firm (Pinnacle Financial): an operational PostgreSQL warehouse and an analytical Snowflake warehouse. As each connection comes online, the workspace shows live KPI tiles ticking up — sources connected, schemas/databases counted, tables profiled, business processes detected — and a workspace-level lens lets the DSA toggle between "all Pinnacle sources" and any individual source.

**Why this priority**: Multi-source is the substrate change the entire feature rests on. Without a workspace abstraction that holds N connections and routes scans/queries to the right child, none of the later stories (cross-source PRDs, semantic layer, validation) can exist. It is also the most visible single change to the user — a new top-level surface.

**Independent Test**: Add two connections (Postgres + Snowflake) on a fresh workspace; verify both cards reach a "live" state with non-zero table and row counts, the workspace KPI strip reflects the merged totals, and the lens selector includes "all sources" plus per-source entries.

**Acceptance Scenarios**:

1. **Given** a fresh workspace with no connections, **When** the DSA adds a PostgreSQL connection with valid credentials, **Then** the connection card progresses through "connecting → scanning → live" within 30 seconds and the workspace KPI strip increments source count, table count, and row count.
2. **Given** a workspace with one live connection, **When** the DSA adds a second connection of a different driver type, **Then** both cards remain live and the lens selector exposes "all sources" plus each source individually.
3. **Given** a connection enters an error state, **When** the DSA inspects the card, **Then** the card surfaces the error reason, a "retry" affordance, and the workspace KPI strip excludes that source's contribution.
4. **Given** an existing single-source workflow run, **When** the workspace is upgraded to multi-source, **Then** the prior session continues to function (single-source remains a valid degenerate case of the workspace).

---

### User Story 2 — Discover the 8 Pinnacle business processes and launch a cross-source PRD with one click (Priority: P1)

After both Pinnacle sources are connected, the DSA lands on Step 1 (Discovery + Pilled PRD). The page automatically detects the eight Pinnacle business processes (AP, Client Fee Billing, CRM, Portfolio Mgmt & Trading, Performance & Asset Reporting, FP&A, GL, HR & Cost Mgmt), shows a coverage matrix indicating which processes exist in each source and where they overlap, and renders six "pilled PRDs" — prebuilt cross-source product suggestions tailored to the discovered schema. Clicking a pill auto-drafts a complete PRD declaring an Iceberg-backed data product as its target.

**Why this priority**: This is the demo's headline moment — the user sees the platform recognize their business, not just their tables. Pills convert raw schema knowledge into a product the customer can name. Without it, the multi-source hub is plumbing without payoff.

**Independent Test**: With both Pinnacle sources connected and seeded, confirm all 8 process cards render with non-zero volume signals (row counts and dollar totals where applicable), the coverage matrix shows at least 3 cross-source overlaps, and at least 6 schema-grounded pills are offered. Clicking any pill produces a draft PRD with a named Iceberg target and listed business questions.

**Acceptance Scenarios**:

1. **Given** both Pinnacle sources are live and seeded, **When** the DSA opens Step 1, **Then** all 8 business-process cards appear within 10 seconds, each displaying name, source backings, volume signal, and last-activity timestamp.
2. **Given** the coverage matrix is rendered, **When** a process exists in both sources with shared business keys (e.g., `client_id`), **Then** that cell is visually marked "ready to combine."
3. **Given** the discovery page is fully loaded, **When** the DSA clicks a pill (e.g., "Client 360"), **Then** Step 2 opens with a pre-drafted PRD containing: cross-source joins identified, declared Iceberg target table name, and a list of business questions the product must answer.
4. **Given** a customer dataset that is not Pinnacle, **When** discovery runs against it, **Then** pills are still generated but reflect that schema (pills are not hardcoded to Pinnacle).
5. **Given** discovery is running, **When** the DSA watches the Step 1 KPI strip, **Then** counters animate for tables scanned, columns profiled, processes detected, cross-source links found, and pills generated.

---

### User Story 3 — Provision a cross-source PRD into an Iceberg data product with a live agent DAG (Priority: P2)

After a PRD is accepted, the DSA clicks "Accept & provision." A new Build page opens showing a live, animated agent DAG: seven agents (schema, pipeline, model, quality, mapping/Iceberg, semantic, delivery) run in dependency order, with active nodes pulsing, completed nodes showing produced artifacts (column lists, model paths, Iceberg table names), and a streaming activity log on the right. KPI tiles tick (rows in motion, agents active, files written, ETA, estimated cost). The run terminates with a registered Iceberg table in the project's catalog.

**Why this priority**: The provisioning experience is what turns a PRD from a document into a delivered product. The agent DAG visualization is the "show your work" moment that distinguishes the platform from a static codegen tool. P2 because P1 must exist first (no PRD = nothing to provision), but it is on the demo critical path.

**Independent Test**: Accept any drafted PRD; verify the Build page renders within 2 seconds, all 7 agents reach completion (or fail with retry), at least one Iceberg table is registered in the catalog, and the KPI strip terminates at non-zero values for rows processed, files written, and elapsed time.

**Acceptance Scenarios**:

1. **Given** an accepted PRD, **When** provisioning starts, **Then** the Build page renders within 2 seconds and the DAG shows all 7 agent nodes with their dependency edges.
2. **Given** a provisioning run is in progress, **When** an agent transitions states, **Then** its node updates within 1 second (active → pulse, complete → checkmark + artifact summary, failed → amber + retry affordance).
3. **Given** an agent fails, **When** the DSA clicks retry, **Then** that agent (and only its downstream dependents) re-runs without restarting completed upstream work.
4. **Given** provisioning completes, **When** the DSA inspects the catalog, **Then** the declared Iceberg table is registered, queryable, and reflects the row count summarized in the final KPI tile.
5. **Given** a CLI user runs the same flow, **When** they request provisioning status, **Then** the same agent states and KPIs are exposed in a text-mode equivalent.

---

### User Story 4 — Ask a cross-source question and get a stitched answer (Priority: P2)

Once a workspace has 2+ connections, the DSA switches the active lens to "all Pinnacle sources" and asks a natural-language question that requires combining both warehouses (e.g., "Show Q1 advisor productivity with AUM growth and meeting count, ranked"). The platform plans the query, pulls bounded subsets from each source, joins them in an in-process scratchpad, and returns the answer with per-source source-chips, the SQL run at each step, and any semantic entities/metrics referenced.

**Why this priority**: Cross-source TTYD is the proof that the hub is more than a UI — it actually queries across sources. It is also the post-provisioning validation surface (Story 7). P2 because it depends on multi-source plumbing (P1) but is independent of the build pipeline (P2 Story 3).

**Independent Test**: With both sources live, ask a question that requires data from both; verify the response includes per-source chips with row counts, an explicit "join in scratchpad" step, and the answer's row count is bounded (≤ 5,000 rows joined; ≤ 250 rows pulled per source).

**Acceptance Scenarios**:

1. **Given** the lens is set to "all Pinnacle sources," **When** the DSA asks a question that needs only one source, **Then** the agent answers from that source alone and the source chips reflect that.
2. **Given** the lens is "all Pinnacle sources," **When** the question requires combining both, **Then** the response shows ≥2 per-source chips and a scratchpad/join chip, each with row counts.
3. **Given** any cross-source query, **When** the planner consults the semantic layer and finds an existing metric definition, **Then** that metric is used (not redefined) and the response indicates a "semantic-layer hit."
4. **Given** any TTYD query, **When** the user attempts to issue a write statement (INSERT/UPDATE/DELETE/DROP/etc.), **Then** the platform blocks it before any source connection executes it.
5. **Given** a query exceeds the per-source 250-row pull cap or the 5,000-row join cap, **When** results are returned, **Then** the response surfaces the truncation explicitly with row counts.

---

### User Story 5 — Build per-connection semantic graphs that grow with each PRD (Priority: P3)

As PRDs ship, each connection's semantic graph accumulates the entities, attributes, metrics, joins, and physical bindings produced by provisioning runs that wrote to that connection's catalog. The DSA can browse a force-directed graph of entities/joins per connection, filter within a graph by domain, and inspect each entity's attributes, metrics, and bindings. Cross-connection reconciliation (merging "the same business concept" across connections into one entity) is **not** performed in v1 — entities remain scoped to the connection that owns them. Cross-source data products materialize into a target Iceberg/catalog connection and live as new entities in *that* connection's graph.

**Why this priority**: The per-connection semantic graph is the compounding asset that makes the redundancy gate (Story 6) work and lets the TTYD planner reuse approved metrics. P3 because it accumulates value across runs but a single demo does not require it to be richly populated — Stories 1–4 stand alone for a first run.

**Independent Test**: After at least one provisioning run completes, the Semantic page shows ≥1 entity in the target connection's graph with ≥1 physical binding, the graph renders without errors, and the connection switcher lets the DSA inspect each connection's graph independently.

**Acceptance Scenarios**:

1. **Given** a successful provisioning run that wrote to a target Iceberg connection, **When** the semantic-agent step completes, **Then** the produced entities and metrics appear in *that connection's* graph on the Semantic page within 5 seconds.
2. **Given** two source connections both contain a similarly-named business concept, **When** the DSA opens the Semantic page, **Then** the two concepts appear as separate entities in their respective per-connection graphs and are NOT auto-merged. (Future-considered: cross-connection reconciliation is on the v2 roadmap.)
3. **Given** a populated per-connection graph, **When** the DSA filters by domain, **Then** the graph and KPI strip update to show only matching entities/metrics within that connection.
4. **Given** the DSA wants to compare concepts across connections, **When** they switch the active connection in the Semantic page, **Then** the view reloads to that connection's graph; no cross-connection overlay is rendered in v1.

---

### User Story 6 — Catch redundancy before building, and validate after (Priority: P3)

Between PRD draft and acceptance, the platform checks the proposed product against the semantic graph and returns a Redundancy Report (🟢 net new / 🟡 partial overlap with reuse-or-override card / 🔴 duplicate, with override-with-rationale). After provisioning completes, a Validation Card auto-runs the PRD's stated business questions against the new Iceberg asset via cross-source TTYD and reports each as ✓ or ✗, with the SQL and a result preview behind each row.

**Why this priority**: Redundancy + auto-validation are the governance/proof bookends around a build. They convert a one-shot codegen demo into a repeatable, auditable workflow. P3 because the build itself works without them — they elevate quality but are not blocking for the first useful demo.

**Independent Test (redundancy)**: Draft a PRD that overlaps an existing semantic entity; confirm the Redundancy Report flags the overlap with a side-by-side reuse-or-override view. Draft a fully novel PRD; confirm a 🟢 net-new result.

**Independent Test (validation)**: Complete a provisioning run; confirm the Validation Card auto-runs each PRD business question, reports ✓/✗ per question, and exposes SQL + result preview on click.

**Acceptance Scenarios**:

1. **Given** a drafted PRD whose entities are absent from the semantic graph, **When** the redundancy gate runs, **Then** the report returns 🟢 net new and acceptance proceeds without blockers.
2. **Given** a drafted PRD that overlaps existing entities or metrics, **When** the report returns 🟡, **Then** a reuse-or-override card lists each overlap and requires an explicit choice before acceptance.
3. **Given** a drafted PRD that fully duplicates an existing product, **When** the report returns 🔴, **Then** acceptance is blocked unless the DSA records an override rationale.
4. **Given** a completed provisioning run, **When** the Validation Card opens, **Then** every business question listed in the PRD has a row in the card and each row resolves to ✓ or ✗ within 30 seconds of the run completing.
5. **Given** a validation row reports ✗, **When** the DSA clicks "Re-plan," **Then** the workflow returns to Step 4 with the failed question pre-loaded as context.

---

### User Story 7 — Standards page enforces conventions on every PRD (Priority: P3)

A read-only Standards page exposes the firm's enterprise conventions: naming rules per source, approved metric definitions (sourced from the semantic layer), PII/PCI/PHI tagging policies (especially relevant for Pinnacle's CRM and HR data), dbt project templates, approved data domains, and Iceberg table standards (partitioning, sort orders, retention). PRD generation in Step 1 consults this page and every generated PRD ends with a "Standards applied" footer listing which standards were enforced.

**Why this priority**: Standards are the governance layer that makes the platform credible to enterprise customers. P3 because the read-only browser and the footer reference are independently shippable from the deeper enforcement logic.

**Independent Test**: Open the Standards page and confirm all six standards categories render with at least one entry each. Generate a PRD and confirm its footer lists ≥1 standard applied.

**Acceptance Scenarios**:

1. **Given** the Standards page is opened, **When** the DSA browses categories, **Then** naming, metrics, PII tagging, dbt templates, domains, and Iceberg standards are all populated.
2. **Given** a PRD is generated in Step 1, **When** the draft is finalized, **Then** the PRD includes a "Standards applied" footer enumerating which standards were enforced.
3. **Given** a metric is defined in the semantic layer, **When** the Standards page is opened, **Then** that metric appears under "approved metric definitions."

---

### Edge Cases

- **Connection partial failure**: One source is live, the other unreachable. The workspace remains usable in single-source mode for the live source; cross-source pills and the "all sources" lens are disabled with an explanatory empty-state, not a silent failure.
- **Schema drift mid-run**: A source's schema changes between discovery and provisioning. The provisioning orchestrator detects the drift, halts at the affected agent, and surfaces a re-discover prompt rather than producing a corrupt artifact.
- **Cross-source query returns empty join**: The scratchpad join produces zero rows. The response explains the empty result with per-source row counts so the DSA can see whether the issue is upstream filtering, key mismatch, or no overlap.
- **PRD acceptance with no semantic graph yet**: First-ever PRD on a fresh install. Redundancy gate returns 🟢 net new without errors; validation runs normally.
- **PRD acceptance with no Iceberg target connection in the workspace**: The platform blocks acceptance with an "Add Iceberg target connection" prompt rather than silently failing or auto-creating a target. Once the user adds an Iceberg/Glue connection, the same PRD can be accepted without re-drafting.
- **Validation question is unanswerable from the new Iceberg asset alone**: The card marks the row ✗ with the reason "required column missing in product" and offers Re-plan. If overall pass rate falls below the FR-031 threshold (default 80%), the product is registered as **provisional** and not yet exposed to TTYD.
- **Validation passes the threshold but some questions still red**: The product is registered as **final** and TTYD-queryable; the ✗ rows remain on the Validation Card and in the activity log as known gaps, and the DSA can choose to re-plan or accept the gap.
- **Demo mode (offline)**: A canned Pinnacle multi-source scenario satisfies all P1/P2 acceptance scenarios without any live database or cloud account.
- **Existing single-source sessions**: Sessions started before the multi-source upgrade continue to work for one minor version (back-compat alias for the prior session-key field).
- **Pill generation against non-Pinnacle data**: Pills reflect the actual discovered schema, not the Pinnacle examples.
- **Concurrent provisioning runs in one workspace**: Each run gets its own Build page and DAG; the workspace activity log captures both with run IDs.
- **Bootstrap re-run after schema change**: Re-running the seed script is idempotent and does not corrupt existing semantic-layer entries tied to the prior schema.

## Requirements *(mandatory)*

### Functional Requirements

#### Workspace & Connections

- **FR-001**: The platform MUST support a workspace abstraction that owns 1..N source connections; single-source operation is a degenerate case of a workspace with one connection. Workspace scope is **per-browser-tab/session**: one workspace per tab, identified by the existing per-tab session UUID, with no server-side persistence of the workspace itself beyond ephemeral cache; closing the tab discards workspace state. Long-lived assets that need to survive a tab close (semantic graph, registered Iceberg data products, activity-log audit records) are persisted independently and keyed by their own identifiers, not by the workspace ID.
- **FR-002**: The platform MUST allow the user to add, list, and remove connections from a workspace, with at minimum the following first-class driver families: PostgreSQL/RDS, Snowflake, Redshift, Databricks, and Iceberg (Glue Catalog). Iceberg/Glue catalog connections are first-class connections explicitly added by the user; the platform does NOT auto-provision a default target catalog.
- **FR-003**: Each connection card MUST display driver label, schema/database count, table count, last-synced timestamp, live/error status, and per-source KPI tiles (rows scanned, tables profiled, processes detected).
- **FR-004**: A workspace KPI strip MUST display merged totals across all live connections (sources connected, total tables, total rows, processes detected, semantic entities derived) and animate as connections come online.
- **FR-005**: The platform MUST provide a workspace-level lens selector with at least "all sources" plus one entry per connection, scoped by schema/database.
- **FR-006**: The session/workspace identifier MUST be backwards-compatible with the prior single-source session field for one minor version after rename.

#### Discovery & Pilled PRDs (Step 1)

- **FR-007**: After connections are live, the platform MUST run business-process discovery per connection and at the workspace level, caching results per source.
- **FR-008**: For the Pinnacle dataset specifically, discovery MUST reliably detect all 8 named business processes: Accounts Payable, Client Fee Billing & Revenue, CRM, Portfolio Management & Trading, Performance & Asset Reporting, Financial Planning & Budgeting, General Ledger, HR & Cost Management.
- **FR-009**: Each business-process card MUST display: process name, domain icon, source backings, volume signal (row count and dollar total where applicable), last-activity timestamp, and an activity sparkline.
- **FR-010**: The platform MUST render a Cross-Source Coverage Map showing which processes exist in which source and visually marking overlapping cells where shared business keys exist.
- **FR-011**: The platform MUST generate at least 6 schema-grounded "pilled PRD" suggestions per workspace; pills MUST be derived from the discovered schema and coverage map, not hardcoded.
- **FR-012**: For the Pinnacle dataset, the six pills MUST include at minimum: Client 360, Revenue Waterfall, Advisor Productivity, Client Profitability, Trade Cost Attribution, and Budget vs. AUM Reality, each declaring an Iceberg table name as its target.
- **FR-013**: Clicking a pill MUST open Step 2 with a pre-drafted PRD containing identified cross-source joins, a declared Iceberg materialization target, and an enumerated list of business questions the product must answer.
- **FR-014**: Step 1 MUST display a KPI strip that animates during discovery: tables scanned, columns profiled, processes detected, cross-source links found, pills generated, and elapsed discovery time.

#### Cross-Source Talk-to-Data

- **FR-015**: When the active lens is "all sources" and a workspace has 2+ live connections, the TTYD agent MUST be able to plan whether a question requires one source or multiple, and execute accordingly.
- **FR-016**: For cross-source questions, the platform MUST pull bounded subsets per source and combine them in an in-process scratchpad before returning the answer.
- **FR-017**: The TTYD response MUST surface per-source chips (driver, scope, row count) and a scratchpad/join chip; expandable details MUST include per-step SQL and any semantic entities/metrics referenced.
- **FR-018**: Read-only enforcement MUST block any non-SELECT/non-WITH statement at every query path, and the system MUST cap per-source pulls at 250 rows and joined results at 5,000 rows.
- **FR-019**: The TTYD planner MUST consult the relevant connection(s)' semantic graphs before query construction (the source connection for single-source questions; the target Iceberg connection for questions answered from already-built data products). Existing metric definitions in the consulted graph MUST be reused rather than redefined, and reuse MUST be reported in the response.
- **FR-020**: A TTYD KPI strip MUST display: queries answered, average latency, sources used today, and semantic-layer hit rate.

#### Semantic Layer

- **FR-021**: The platform MUST maintain a persistent, versioned semantic graph **per connection**, composed of entities, attributes, metrics, joins, and physical bindings local to that connection. Each connection owns its own graph; durable storage is keyed by a stable connection identifier so the graph survives tab close.
- **FR-022**: The platform MUST NOT auto-reconcile entities across connections in v1. A business concept that appears in two source connections (e.g., a `clients` dimension in Postgres and a `dim_client` in Snowflake) remains as two separate entities in two separate per-connection graphs. Cross-source data products are still produced via provisioning (Story 3), but the resulting entities live only in the target Iceberg/catalog connection's graph. *Future consideration: v2+ may introduce a workspace-level or project/firm-level unified graph that reconciles across connections.*
- **FR-023**: *(reserved — was: reconciliation diff for ambiguous cross-source matches; deferred with FR-022 to v2+)*
- **FR-024**: A Semantic page MUST render each connection's graph as a force-directed view, with a connection switcher to move between graphs and a per-graph filter by data domain. A per-connection header KPI strip MUST display entities, metrics, joins, bindings, and % of that connection's detected processes mapped.
- **FR-025**: The semantic layer MUST be read-only via the UI; writes occur only through the PRD acceptance/provisioning flow, which writes to the target connection's graph.

#### Redundancy Gate & Provisioning

- **FR-026**: Between PRD draft and acceptance, the platform MUST run a redundancy check against the **target connection's** semantic graph (the connection where the new product will be materialized — typically an Iceberg/catalog connection) and return a report with three states: net-new (proceed), partial overlap (require reuse-or-override decision), full duplicate (block unless override rationale recorded). The check does NOT scan source connections' graphs in v1.
- **FR-027**: PRD acceptance MUST initiate a provisioning run executing at least 7 agent steps in dependency order: schema, pipeline, model, quality, mapping (Iceberg/catalog registration), semantic, delivery.
- **FR-028**: Provisioning MUST stream live progress events such that a Build page can render a DAG with per-node states (active/complete/failed), produced artifacts on completion, and inline retry on failure.
- **FR-029**: A failed agent MUST be retryable in isolation; only its downstream dependents (not completed upstream work) re-execute.
- **FR-030**: The Build page MUST display live KPI tiles: rows in motion, agents active, pipeline latency p95, files written, estimated cost, and ETA — driven from the same provisioning event stream.
- **FR-031**: Provisioning MUST terminate by registering the declared Iceberg data product in the workspace's user-added Iceberg/Glue catalog connection. The product is registered as **final and TTYD-queryable** only if the auto-validation pass rate (FR-033) is ≥ a configurable threshold (defaulting to 80%, matching SC-004). If the pass rate is below threshold, the product MUST be registered in a **provisional** state — present in the catalog and visible in the Semantic page and activity log, but NOT exposed as a TTYD-queryable source until a subsequent rerun lifts the pass rate to ≥ threshold. PRD acceptance MUST be gated on the workspace containing at least one live Iceberg/Glue connection; if none is present, the platform MUST surface an "Add Iceberg target connection" prompt and block provisioning rather than silently fail or auto-create a target.
- **FR-032**: A workspace activity log MUST capture the full chain — discovery → pill click → PRD → redundancy decision → provisioning → validation — as the audit trail for the run.

#### Auto-Validation (Prove-It Loop)

- **FR-033**: After provisioning completes, the platform MUST automatically run each business question listed in the PRD against the new Iceberg asset via cross-source TTYD.
- **FR-034**: A Validation Card MUST display each question with an in-progress spinner that resolves to ✓ or ✗; clicking a row MUST reveal the SQL run and a result preview.
- **FR-035**: A failed validation MUST expose a "Re-plan" affordance returning to Step 4 with the failed question loaded as context. When the run's pass rate is below the registration threshold (FR-031), the Build page MUST surface a "needs re-plan" status banner and a "Re-run from failed step" affordance that re-executes only the failed-question path (not full provisioning) where possible. A successful rerun that lifts the pass rate to ≥ threshold MUST promote the previously-provisional product to final and expose it to TTYD.
- **FR-036**: A validation KPI strip MUST display: questions auto-validated, % passing, average query latency, semantic-layer hit rate, and Iceberg scan bytes.

#### Standards

- **FR-037**: A read-only Standards page MUST expose at least six categories: naming conventions, approved metric definitions, PII/PCI/PHI tagging policy (informational only in v1 — see Clarifications Q4), dbt project templates, approved data domains, and Iceberg table standards.
- **FR-038**: PRD generation in Step 1 MUST consult Standards and produce drafts conformant with them; every generated PRD MUST end with a "Standards applied" footer enumerating which standards were enforced.

#### Cross-Cutting

- **FR-039**: All existing single-source acceptance tests (51 pytest + the vitest cascade-invalidation suite) MUST continue to pass without modification beyond the documented session-field rename alias.
- **FR-040**: Every new capability reachable from the React UI MUST have a text-mode CLI equivalent (three-frontend rule), and the Streamlit demo app MUST continue to function for single-source flows.
- **FR-041**: The platform MUST provide a demo mode that reproduces the full multi-source narrative (connect → discover → pill → provision → validate → TTYD) without any live database or cloud account.
- **FR-042**: The bootstrap script MUST seed the operational PostgreSQL warehouse with the eight Pinnacle business processes at the row volumes named in this spec, and the analytical Snowflake warehouse MUST share business keys (`client_id`, `account_id`, `strategy_id`) with the operational source. **Implementation note (2026-04-26):** the live `platform-agent-pinnacle` RDS instance lays out the 8 processes as **per-process schemas** (`ap.`, `billing.`, `crm.`, `gl.`, `hr.`, `performance.`, `planning.`, `portfolio.`) rather than a flat `public` namespace — a stronger design that makes business-process membership explicit at the schema level. Two volume departures from the named targets are accepted as-shipped: `planning.budget_line` carries **480** rows instead of 18,432 (driven by a 24-period × 20-line layout rather than the spec's 16×8×24×6 grid); `billing.billing_cycle` carries **24** rows instead of 1,610 closed + 70 open (one cycle per fiscal period, with the 1,680 fee invoices attaching to those 24 cycles instead of denormalizing into 1,680 cycles). All other named volumes match exactly. Seed reproducibility is captured in `scripts/seed_pinnacle.sql` (15,415 INSERT statements via `pg_dump`); see `scripts/regenerate_pinnacle_seed.sh` for the regeneration path.
- **FR-043**: All architectural decisions made while implementing this feature MUST be recorded as ADRs at the moment of decision (per constitution Addendum E), including at minimum: multi-connection workspace, semantic graph storage, cross-source query approach, redundancy gate, provisioning orchestration into Iceberg, and pill generation.

### Key Entities *(include if feature involves data)*

- **Workspace**: A per-browser-tab working context, identified by the existing per-tab session UUID. Owns N connections in-memory for the lifetime of the tab and scopes the lens selector. Has no server-side persistence beyond ephemeral cache; durable assets (semantic graph entries, registered Iceberg products, audit-log entries) survive tab close via their own persistence layers, not via the workspace.
- **Connection**: A live binding to a single source warehouse (driver type, credentials reference, scope, last-synced timestamp, status). Contributes its discovered tables and processes to the workspace.
- **Business Process**: A domain-level activity inferred from schema + data (e.g., Accounts Payable). Carries source backings, volume signal, last-activity timestamp, sparkline series.
- **Pilled PRD**: A schema-grounded suggestion for a cross-source data product. Carries title, source backings, declared Iceberg target, estimated build time, and seeds for the PRD body.
- **PRD (Product Requirements Doc)**: A persisted draft containing identified joins, declared materialization target, business questions, and a Standards-applied footer. Inputs to redundancy gate and provisioning.
- **Redundancy Report**: The output of the gate between PRD draft and acceptance: state (net-new/partial/duplicate), overlapping entities/metrics, reuse-or-override decisions captured.
- **Provisioning Run**: A single execution of the agent pipeline. Carries run ID, agent states, produced artifacts, KPI series, and terminal status. One per accepted PRD.
- **Iceberg Data Product**: The terminal artifact of a provisioning run — a registered Iceberg table with associated dbt models, semantic-graph entries, and (when validation passes the threshold) TTYD exposure. Has two states: **final** (≥ threshold validation pass rate; TTYD-queryable) and **provisional** (below threshold; not TTYD-queryable; promotable on successful rerun).
- **Semantic Entity**: A business concept (e.g., Client) with attributes, metrics, joins, and ≥1 physical bindings — **scoped to a single connection** in v1. The same business concept appearing in two connections produces two separate entities.
- **Physical Binding**: A specific table × column-map within a single connection that backs a semantic entity.
- **Validation Result**: The auto-run answer to one PRD business question (✓/✗, SQL, result preview, latency).
- **Workspace Activity Log Entry**: A timestamped record of a workflow event (connection added, discovery completed, pill clicked, PRD accepted, agent state change, validation result), forming the audit trail.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A DSA can complete the full Pinnacle showcase narrative — connect both source warehouses (Postgres + Snowflake; the Iceberg/Glue target connection MAY be pre-staged in the workspace ahead of the live demo), discover, pick a pill, accept through the redundancy gate, watch provisioning, see the Validation Card go green, and ask a fresh cross-source TTYD question against the new product — in under 8 minutes live.
- **SC-002**: From a fresh workspace, the time from "second connection added" to "all 8 Pinnacle business processes visible as cards" is under 60 seconds at the seeded data volumes.
- **SC-003**: At least 6 schema-grounded pills appear on Step 1 for the Pinnacle dataset; the rate at which a pill click yields a complete cross-source PRD draft (with target, joins, business questions) is 100%.
- **SC-004**: Provisioning a pilled PRD produces a registered Iceberg table; the run's Validation Card reports ≥ 80% green on the PRD's stated business questions on the first run, which clears the registration threshold (FR-031) and exposes the product as TTYD-queryable. Below-threshold runs register the product as **provisional** (catalog-visible, semantic-graph-recorded, but not TTYD-queryable until a successful rerun lifts the pass rate).
- **SC-005**: Cross-source TTYD answers a question requiring both Pinnacle sources within 5 seconds at the seeded data volumes, with per-source chips and a scratchpad/join chip surfaced in the response.
- **SC-006**: Read-only enforcement blocks 100% of attempted write statements across every query path (TTYD, scan, profile) without ever forwarding them to a source.
- **SC-007**: Single-source workflow regression: 100% of the prior pytest + vitest suite continues to pass after the workspace rename, with no new flakes attributable to the multi-source rework.
- **SC-008**: The workspace activity log captures every step of the chain (discovery → pill → PRD → redundancy → provisioning → validation) with timestamps such that an audit reviewer can reconstruct the run from the log alone.
- **SC-009**: Demo-mode (offline) can reproduce the full multi-source narrative for SC-001 with zero live database or cloud dependency.
- **SC-010**: A non-Pinnacle dataset run end-to-end produces pills, processes, and a registered Iceberg product reflecting that schema (not Pinnacle-named outputs) — proving the workflow is schema-driven rather than dataset-specific.
- **SC-011**: Every PRD generated in Step 1 ends with a non-empty "Standards applied" footer.
- **SC-012**: 100% of architectural decisions made during implementation land as ADRs in the same commit/PR that introduces the decision (per constitution Addendum E).

## Assumptions

- The two demo sources both represent the same firm (Pinnacle Financial) and share business keys (`client_id`, `account_id`, `strategy_id`) — the operational PostgreSQL side and the analytical Snowflake side are intentional mirrors of one company.
- Iceberg is the explicit materialization target for cross-source data products; the existing 5-agent Snowflake → Iceberg migration suite is the foundation extended (with two new agents: semantic and delivery) for the provisioning orchestrator.
- Single-source operation remains a valid, supported mode — multi-source is additive, not a replacement.
- Read-only is the default posture for every query path; bounded row caps (250 per source pull, 5,000 per joined result) are acceptable for the demo and analytical reads.
- The user driving the demo is technical (DSA / data engineer), not an end business user — the UX optimizes for "show your work" credibility, not consumer simplicity.
- Existing dark-theme aesthetic (Instrument Serif headers, JetBrains Mono body, established accent palette) is preserved; this feature does not introduce a new design system.
- AWS profile, region, and Bedrock model availability follow the pre-existing project conventions (see CLAUDE.md). Snowflake authentication via SSO/externalbrowser remains the supported path for live demos.
- Per-user RBAC on the semantic graph, write-back to source systems beyond DDL extensions and new tables, additional cost optimization beyond MetricFlow + Iceberg defaults, a standalone Iceberg-suite UI, **cross-connection semantic reconciliation** (auto-merging the same business concept across two source connections into one unified entity), and **active PII/PCI/PHI enforcement** (auto-detection, response banners, activity-log tag tracking, masking, blocking) are explicitly out of scope for v1. Cross-connection reconciliation is on the v2+ roadmap as either a workspace-level or a project/firm-level unified graph; PII enforcement is on the v2+ roadmap as a layered scope (tag → display + log → mask → block). The v1 data model intentionally does not preclude either path.
- The provisioning orchestrator's underlying agents (schema, pipeline, model, quality, mapping) already exist in the migration-suite codebase and are reused; semantic and delivery are net-new but follow the same agent contract.
- ADRs 016–021 (or equivalent numbering at implementation time) will be authored in-flight per constitution Addendum E for the six major architectural decisions (multi-connection workspace, semantic graph storage, cross-source query approach, redundancy gate, provisioning orchestration into Iceberg, pill generation).
