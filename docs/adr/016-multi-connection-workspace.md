# ADR-016: Multi-Connection Workspace — Per-Tab/Session Scoping

**Status**: Accepted (initial decisions landed in-flight with feature `002-dsa-hub-pinnacle` Phase 2 commits)

**Date**: 2026-04-26

**Feature**: `specs/002-dsa-hub-pinnacle/`

## Context

The platform is evolving from a single-source workflow into a multi-source hub where one or more sources (PostgreSQL, Snowflake, Redshift, Databricks, Iceberg/Glue) are unified under a single user-facing **Workspace**. The existing single-source identity is the per-tab session UUID (`frontend/src/lib/session.ts`); we have to decide whether the new Workspace concept extends that identity, replaces it, or introduces a parallel one.

Three options were on the table at `/speckit.clarify` (Q1):

A. **Per-tab/session** — workspace lives only in the browser session; closing the tab discards it.
B. **Per-user** — workspace owned by an authenticated user; one user may have multiple workspaces.
C. **Per-firm/tenant** — workspace shared across users within a tenant; per-user RBAC remains OOS but the data model supports it.
D. **Hybrid** — local mode is per-tab; deployed mode is per-user.

## Decisions

### D1 — Workspace scope = per-tab/session (Q1, Option A)

**Decision**: A Workspace is identified by the existing per-tab session UUID. There is one Workspace per browser tab. State is held in browser `sessionStorage` + a backend in-memory `WorkspaceRegistry`; nothing persists server-side beyond ephemeral cache. Closing the tab discards Workspace state.

**Rationale**: The per-tab UUID model is already battle-tested in feature 001 (its invariants: one UUID per tab, lost on close, never reused). Reusing it for Workspace identity:

- Avoids a parallel identity scheme that downstream code would have to bridge.
- Matches the demo-driver persona — a DSA running a customer demo wants the workspace to dissolve when they close the tab so the next demo starts clean.
- Defers the much harder identity questions (multi-user RBAC, per-firm partitioning, credential lifecycle) to v2+ without locking out either path.

The data model is intentionally permissive in this respect: long-lived assets (semantic graph, registered Iceberg products, audit log) are scoped by their own identifiers (per ADR-017), not by Workspace, so the v2+ migration to per-user or per-firm Workspaces does not require touching the durable assets.

### D2 — Back-compat header alias

**Decision**: The backend accepts `X-DSA-Workspace-ID` as a synonym for `X-DSA-Session-ID` for one minor version (FR-006). When only the alias is supplied, a deprecation warning is logged. After one minor version the alias is removed.

**Rationale**: Allows frontends to migrate to the more semantically accurate `X-DSA-Workspace-ID` name without an atomic flag-day. Short window because the canonical UUID is unchanged — only the header name differs.

### D3 — Workspace registry is in-memory and process-scoped

**Decision**: `WorkspaceRegistry` (`src/platform_agent/workspace/registry.py`) is a thread-safe in-memory map. Process restart loses all Workspaces. Drivers (per-Connection `DatabaseDriver` instances) are held in a sibling `MultiSourceDriver` registry per Workspace; they are reconnected lazily as Connections re-enter the `connecting → scanning → live` lifecycle.

**Rationale**: Per D1, Workspaces are inherently ephemeral. Adding cross-restart persistence would only matter for the case where the user's tab survives a backend restart — which is rare during a demo and in deployed mode is handled by the load balancer keeping at least one healthy backend. The cost (a persistence layer for ephemeral records, plus reconciliation logic on restart) is not worth that edge case.

## Consequences

- **Demo flow stays clean**: every fresh tab starts with an empty Workspace; the DSA does not have to manually clear stale state before a demo.
- **Multi-user is explicitly deferred**: any feature that requires per-user RBAC or shared workspaces is on the v2+ roadmap.
- **Credentials are per-tab too**: connection credentials are held in backend session memory keyed by the per-tab UUID and never persisted to disk in local mode (deployed mode uses Secrets Manager ARNs).
- **No back-compat for the alias beyond one minor version**: callers must migrate to `X-DSA-Session-ID` (the canonical name) or accept removal.

## Future considerations

The data model intentionally does not preclude:

- **Workspace-scoped unification** (Q2 option 2 — workspace-level semantic graph reconciling across Connections). Would require a workspace-level store keyed by Workspace UUID *plus* a stable upgrade path for current per-Connection stores.
- **Project/firm-scoped unification** (Q2 option C — per-firm semantic graph). Would require a stable `project_id` derivation (e.g., hash of canonical source URLs) and a migration step that copies per-Connection entries into the project-level store.

Both are explicitly out of scope for v1.
