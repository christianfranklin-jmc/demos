# ADR-021: Pill Generation — Schema-Grounded with Few-Shot Pinnacle Examples

**Status**: Accepted in two stages — D1 (deterministic v1) lands now with the
US2 contract surface; D2 (Strands/Bedrock LLM agent) will be amended in-flight
when the LLM path replaces the deterministic Pinnacle catalog.

**Date**: 2026-04-26

**Feature**: `specs/002-dsa-hub-pinnacle/`

## Context

FR-011, FR-012, and SC-010 require ≥6 schema-grounded pill suggestions on the
Step-1 Discovery page. For the Pinnacle showcase, six specific pills must
appear (Client 360, Revenue Waterfall, Advisor Productivity, Client
Profitability, Trade Cost Attribution, Budget vs. AUM Reality). For non-
Pinnacle datasets, pills must reflect *that* schema rather than a hardcoded
Pinnacle list.

Research item R5 chose few-shot prompting against an Opus 4.7 Strands agent
with the six Pinnacle pills as in-context examples. Implementing the LLM
path requires Bedrock setup, prompt files, eval cases, and credentials —
substantially more scaffolding than the contract surface that depends on it.

## Decisions

### D1 — v1 is deterministic, schema-grounded, with the same external contract (US2 ships now)

**Decision**: The v1 `pill_generator` (`src/platform_agent/tools/pill_generator.py`)
is a pure-Python module that generates pills deterministically:

- Pinnacle path: when both Postgres (with ≥6 of the 8 named process schemas
  present) and Snowflake are live, return the six named pills verbatim.
  Each pill carries a complete `seed_prd_body` PRDDraft with a
  fully-qualified `iceberg.pinnacle_360.fct_<name>` target, business
  questions, source pulls per connection, and a four-entry
  `standards_applied` footer (SC-011 satisfied at the contract level).
- Heuristic fallback: for non-Pinnacle datasets, generate one pill per
  business process that appears in ≥2 connections (cross-source-overlap),
  padding with single-source pills until `min_pills` is satisfied.
- Iceberg target connection_id resolution: if a `driver_type=iceberg`
  connection is present in the workspace, its connection_id is the
  target; otherwise the sentinel `ICEBERG_TARGET_REQUIRED` is used.
  Provisioning gate (FR-031) blocks acceptance until a real Iceberg
  connection exists.

**Rationale**: The v1 contract — `POST /workflow/pills` returns ≥6 schema-
grounded pills with complete PRD bodies, `POST /workflow/pills/{id}/draft-prd`
returns the seeded PRD — is what the frontend (T058–T064) depends on. That
contract is identical whether pills come from a deterministic generator or
an Opus 4.7 agent. Shipping the deterministic version unblocks Step 1
Discovery without waiting for full agent infrastructure (system prompts,
Bedrock model wiring, eval infrastructure). The LLM swap is a single-
function replacement at `tools/pill_generator.generate_pills()`.

The deterministic Pinnacle path also gives us a stable acceptance baseline:
the six named pills will always appear when the workspace looks like
Pinnacle, so SC-010 / FR-012 remain testable across LLM model upgrades.

### D2 — v2 LLM path (Opus 4.7, few-shot Pinnacle examples) — TBD

*Decision pending; will be amended into this ADR in the same commit that
introduces the Strands agent.*

Outline:
- `pill-agent` Strands agent (Opus 4.7 per R5 — pill generation is the
  cross-source reasoning task most likely to need Opus's multi-table
  judgment).
- System prompt at `src/platform_agent/prompts/pill_agent.md` includes
  the six Pinnacle pills as in-context few-shot examples (not as a
  hardcoded answer set — the agent must produce schema-grounded pills
  that reflect the actual scanned schema, regardless of dataset).
- Inputs: per-connection discovery summary + cross-source CoverageMatrix.
- Output: same `PillSuggestion` shape as the deterministic generator.
- Eval cases under `eval/test_cases/pill_agent.json` (T049): ≥8 cases
  covering Pinnacle (must produce the six named pills) + non-Pinnacle
  schemas (must NOT produce Pinnacle titles, per SC-010).

Once D2 lands, the deterministic Pinnacle path becomes a fallback
("offline mode") preserving the demo when Bedrock is unavailable
(FR-041, R9).

## Consequences

- **D1 (now)**: Step 1 discovery is fully testable today. The Pinnacle
  showcase narrative (SC-001) is reachable end-to-end via the
  deterministic generator, no AWS dependencies.
- **D1 → D2**: The `generate_pills()` function signature stays stable; the
  LLM swap touches only its body. No frontend or contract changes
  required.
- **Eval infrastructure**: T049 (eval cases) lands with D2 since the
  deterministic v1 has no LLM to evaluate. The deterministic v1 is
  covered by `tests/contract/test_pills.py` instead.

## Alternatives considered

- *Skip the deterministic path; ship the LLM path directly*: rejected —
  introduces Bedrock setup as a hard dependency for Step 1, slows down
  US2 by an order of magnitude, and forces the LLM to be reliable for
  the demo before anything else can be tested.
- *Hardcoded pill catalog without any schema check*: rejected — violates
  SC-010 (non-Pinnacle datasets would still produce Pinnacle pills).
- *Sonnet 4 for pill generation*: rejected per R5 — pill generation needs
  the cross-source reasoning judgment that Opus 4.7 is escalated for.

## Forward-references

- ADR-019 (redundancy gate) — runs against the target Iceberg connection's
  semantic graph after a pill is clicked and the PRD is drafted.
- ADR-020 (provisioning orchestration) — receives the PRD and materializes
  the declared Iceberg target.
