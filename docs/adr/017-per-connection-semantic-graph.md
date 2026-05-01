# ADR-017: Per-Connection Semantic Graph Storage

**Status**: Accepted (initial decisions landed in-flight with feature `002-dsa-hub-pinnacle` Phase 2 commits)

**Date**: 2026-04-26

**Feature**: `specs/002-dsa-hub-pinnacle/`

## Context

With Workspaces declared per-tab (ADR-016), durable cross-session assets — the semantic graph, the registered Iceberg product index, and the activity log — need a separate identity that survives tab close. The clarification (`/speckit.clarify` Q2) chose **per-connection** scoping over per-firm or single-global alternatives.

This means each Connection (PostgreSQL, Snowflake, Iceberg/Glue, etc.) owns its own:

- Semantic graph (entities, attributes, metrics, joins, physical bindings)
- Registered Iceberg products (only meaningful for `driver_type=iceberg` Connections)
- Activity log entries scoped to actions on that Connection
- Discovery cache (most recent `scan_metadata` snapshot)

In v1 the platform does **not** auto-reconcile entities across Connections. The same business concept appearing in two source connections produces two separate entities in two separate stores. Cross-source data products *do* materialize via provisioning — the result lives in the target Iceberg connection's store, not unified anywhere upstream.

## Decisions

### D1 — Per-connection storage, keyed by content-addressed `connection_id`

**Decision**: Each Connection owns its own durable store keyed by `connection_id = SHA-256(driver_type | normalized_endpoint | scope)`. Two tabs that point at the same source compute the same `connection_id` and reattach to the same store; closing a tab and reopening a fresh one produces the same id and the durable assets reappear.

**Rationale**: Per Q2, the spec contract is that each Connection has its own graph. Content-addressing makes the identity stable across sessions without any server-side bookkeeping (no IDs handed out, no reconciliation of "is this the same source?"). Normalization (lowercase host, lowercase scope, alias-collapsed driver type) prevents trivial drift (e.g., `Postgres` vs `postgresql`, `HOST` vs `host`).

### D2 — Local backend = SQLite per Connection

**Decision**: In local mode (default), each Connection's store is a SQLite database file at `~/.dsa-hub/connections/<connection_id>/store.db` (override via `DSA_HUB_CONNECTIONS_DIR`). Tables: `entities`, `physical_bindings`, `metrics`, `joins`, `products`, `activity_log`, `discovery_cache`. Migrations applied idempotently on first open.

**Rationale**: SQLite is the simplest local store with first-class Python support, zero deploy footprint, and ACID transactions — exactly the right shape for "ephemeral workspace, durable per-connection storage." One file per connection physically isolates each connection's graph and matches Q2's no-cross-connection-reference invariant by construction.

### D3 — Deployed backend = single-table DynamoDB

**Decision**: In deployed mode (`STORAGE_BACKEND=dynamodb`), all Connections share one DynamoDB table `DSAHubConnectionStore` with PK `connection_id` and SK `entity_kind#entity_id`. A sparse GSI on `(connection_id, kind)` supports kind-scoped queries.

**Rationale**: Matches the existing AgentCore Memory single-table pattern (ADR-011). PK partitioning keeps every Connection's entries physically co-located, which keeps the no-cross-connection-reference invariant intuitive in queries.

### D4 — No public write endpoint for the semantic graph

**Decision**: Reads are exposed via `GET /semantic/graph?connection_id=…` and `GET /semantic/entities/{entity_id}`. Writes happen only through the provisioning flow's `semantic-agent` (ADR-020), which writes to the target Connection's store as part of materializing a PRD into an Iceberg product.

**Rationale**: Keeps the graph an emergent record of provisioning activity rather than a free-form editable dataset. Users who want to "edit" entities do so by editing the PRD and re-provisioning, which records the change in the activity log automatically. Avoids the entire RBAC / write-conflict surface for v1.

### D5 — Cross-connection reconciliation deferred

**Decision**: V1 makes no attempt to merge "the same business concept" across Connections. Each store is independent.

**Rationale**: Reconciliation is a non-trivial LLM problem and would require a workspace-level or project-level store as a target. Both are on the v2+ roadmap (ADR-016 future considerations). Deferring it keeps v1's data model simple and lets us prove the workflow without first solving identity disambiguation.

### D6 — Activity log is append-only and per-connection

**Decision**: The activity log lives in each Connection's store. An action is logged against the Connection that "owns" it: a discovery hit lands in the source Connection's log; a registration lands in the Iceberg Connection's log; a redundancy decision lands in the target Iceberg Connection's log. Append-only — no edits or deletes. SQLite ordering is `(ts DESC, rowid DESC)` so equal timestamps fall back to insertion order.

**Rationale**: Per FR-032 + SC-008, an audit reviewer must be able to reconstruct a run from the log alone. Append-only is the cleanest invariant; per-connection scoping keeps the log fragments naturally close to the durable assets they describe. Reconstruction across Connections is straightforward — the run's activity is sequenced by `(connection_id, ts)`.

## Consequences

- **No silent server-side state**: Workspaces dissolve, but graphs/products/log persist. A DSA who reopens a tab tomorrow and re-adds their connections sees yesterday's graph.
- **Local-mode simplicity**: A `rm -rf ~/.dsa-hub/connections/` is a clean reset; useful for debugging and demo prep.
- **No cross-connection joins in storage**: Cross-source data products land in the Iceberg connection's store and are queryable from there, but the source connections' graphs never reference the target's entities. Redundancy gates check the target only.
- **Migration path to v2+ is mechanical**: A future workspace-level or project-level store would consume the per-connection stores as inputs to an LLM-driven reconciliation pass. Nothing in v1 forecloses that.

## Forward-references

- ADR-019 (redundancy gate) consumes only the *target* Connection's graph.
- ADR-020 (provisioning + Iceberg driver + palette) writes new entities into the target Connection's graph via the `semantic-agent`.
