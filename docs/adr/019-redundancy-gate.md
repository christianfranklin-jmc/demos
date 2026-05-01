# ADR-019: Redundancy Gate Against the Target Connection's Graph

**Status**: Accepted (D1 — deterministic v1) in feature `002-dsa-hub-pinnacle` Phase 8 backend. D2 (Strands LLM redundancy-agent) reserved for in-flight amendment.

**Date**: 2026-04-26 (D1); D2 amended when the LLM redundancy-agent lands.

**Feature**: `specs/002-dsa-hub-pinnacle/`

## Context

US6 + FR-026 add a deliberate human gate between PRD draft and acceptance: before the orchestrator runs, the platform compares the proposed product against existing entities/metrics in the **target connection's** semantic graph and surfaces a report with three states:

- `net_new` — no overlaps; acceptance proceeds without blockers.
- `partial_overlap` — at least one entity or metric matches; acceptance is blocked until the user records reuse-or-override decisions per overlap.
- `duplicate` — every proposed entity matches with high attribute overlap; acceptance is blocked unless an override rationale is recorded.

Per Q2 the gate scans **only** the target connection's graph. Source connections are never compared (they hold raw schema entities like `clients` and `accounts` that always overlap with anything that selects from those sources — comparing them would surface false positives).

## Decisions

### D1 — Deterministic name + attribute overlap (Phase 8, T115 + T117)

**Decision**: Implemented `src/platform_agent/api/routes_redundancy.py`. Two endpoints:

- `POST /workflow/redundancy-check` — accepts a `PRDDraft`, reads `entities_proposed` and `metrics_proposed` against the target Iceberg connection's `ConnectionStore`, returns a `RedundancyReport`.
- `POST /workflow/redundancy-check/{report_id}/decide` — records reuse-or-override decisions per overlap; flips `cleared_to_provision` when conditions are met.

State derivation:

- For each proposed entity: name match (case-insensitive) → compute attribute-name set overlap percentage = `|proposed ∩ existing| / |proposed| × 100`.
- For each proposed metric: name match → 100% if `definition_sql` strings match (lowercased), else 50%.
- Final state:
  - `net_new` if no overlaps.
  - `duplicate` if every proposed entity/metric has an overlap AND every overlap is ≥80%.
  - `partial_overlap` otherwise.

Clearance rules in `decide()`:

- `net_new` → cleared automatically (returned as-is from the check).
- `partial_overlap` → cleared once every overlap has a recorded decision (kind=`reuse` or kind=`override` with non-empty rationale).
- `duplicate` → cleared only when an `override_rationale` is supplied at the report level AND at least one decision is kind=`override`.

The provision route (`POST /workflow/provision`) consults the report when `redundancy_report_id` is supplied and rejects with `400 redundancy_not_cleared` if `cleared_to_provision` is false. Callers without a report id continue to use the soft `redundancy_cleared=True` flag for demo flows; that path will be removed when the gate becomes mandatory in v2.

**Rationale**: A deterministic v1 lets US6 ship the gate UX immediately. The contract surface (`POST /redundancy-check`, `POST /decide`) is identical to what an LLM-driven `redundancy-agent` would expose, so the swap to an Opus 4.7 reasoning pass per R7 is a single-function replacement (similar to ADR-018 and ADR-021 patterns).

The gate is also conservative on purpose: name-based matching catches the obvious "you already have a `client` entity" case without flagging every entity that happens to share an attribute name.

**Alternatives considered**:
- *LLM-as-judge for v1*: rejected — too much scaffolding for a P3 ship; the deterministic heuristic catches the demo-critical overlaps reliably and the swap path is clear.
- *Always block on partial_overlap (no per-overlap decisions)*: rejected — too rigid; users with legitimate "extend this entity" intentions would get a hard 'no' on a soft signal.
- *Cross-connection scan*: rejected per Q2 — produces false positives because source connections hold raw schema entities that always look "redundant" with any consuming PRD.

### D2 — Strands LLM redundancy-agent — TBD

The LLM-driven path (R7 D2) plugs in above this layer: an `redundancy-agent` (Opus 4.7) consumes the same `target_connection_id` graph snapshot + the `PRDDraft` and produces a richer report with semantic similarity (not just name match) and a synthesized side-by-side diff. The contract surface stays identical; only the body of `routes_redundancy.post_check()` changes.

## Implementation surface (D1)

- `src/platform_agent/api/routes_redundancy.py` — both endpoints (~245 LOC). In-memory `_reports` registry keyed by `report_id`.
- Provision route (`routes_workflow_provision.py`) hardened: when `redundancy_report_id` is supplied, the report is looked up and `cleared_to_provision` is enforced.
- `tests/contract/test_redundancy.py` — 5 tests: 400 no_iceberg_target; net_new on empty store; partial_overlap blocks until decisions recorded; duplicate requires override_rationale; 404 for unknown report.

## Consequences

- **Soft gate today, hard gate when LLM lands**: callers without a `redundancy_report_id` still pass the v1 default `redundancy_cleared=True`. v2 will make the report id mandatory once the agent's report is reliable enough.
- **No write to source connections**: the gate is read-only against the target connection's graph; source-connection graphs are untouched (Q2 invariant).
- **Activity log captures the decision**: `REDUNDANCY_DECISION` entries record the report id, state, overlap count, and whether auto-cleared.

## Forward-references

- ADR-018 D2 (cross-source NL→SQL planner) and ADR-021 D2 (pill generator) follow the same D1 (deterministic) → D2 (LLM swap) pattern.
- ADR-020 D2 (provisioning orchestrator) consumes the cleared report.
