# Implementation Plan: DSA Frontend × PlatformAgent Backend Integration

**Branch**: `001-dsa-agent-integration` | **Date**: 2026-04-17 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-dsa-agent-integration/spec.md`

## Summary

Combine the DSA MVP's polished 4-step React workflow (Requirements → Conceptual → Logical → Detailed Spec) with PlatformAgent's Strands/Bedrock agent backend so the UX is driven by real AI agents and real database introspection instead of pre-scripted content. Import the DSA frontend from `dsa/feat-enhancements-erd-visuals` into `frontend/` (replacing the PlatformAgent React scaffold while preserving `agentcore-client/` and `auth.ts`), rewrite `useAgent.ts` to call a step-scoped PlatformAgent backend over SSE, and expose Step 4 dbt artifacts as browser-downloadable zips. Streamlit and CLI stay untouched. Existing AgentCore Runtime/Gateway/Memory/Cognito/Amplify resources continue serving unchanged.

Clarified constraints (from `/speckit.clarify`, captured in ADR-015 D3–D7):
- Scale: up to 10 concurrent phData users.
- Credentials: strictly session-scoped; no persistence layer.
- Session ID: per-browser-tab UUID in `sessionStorage`; keys AgentCore Memory.
- Long-running operations: keepalive-driven over SSE — 30s silence = failure; cancel always available.
- Deployed-mode dbt delivery: in-memory zip streamed to browser; no new S3 module.

## Technical Context

**Language/Version**: Python 3.12+ (backend, agents, Lambda tools); TypeScript 5.6 + React 18 (frontend) per Constitution Article II.
**Primary Dependencies**:
- Backend: `strands-agents`, `boto3` (Bedrock + Cognito), `fastapi` (thin SSE wrapper in front of the existing `BedrockAgentCoreApp`), `pydantic` v2 (models/contracts), `python-dotenv`, `opentelemetry-instrumentation-*` (existing).
- Frontend: `react@18`, `react-dom@18`, `@xyflow/react@12` (ERD), `tailwindcss@4`, `vite@6`, `typescript@5.6`, `aws-amplify` (Cognito PKCE). Preserve existing `frontend/src/lib/agentcore-client/` (SSE parsers) and `frontend/src/lib/auth.ts` from PlatformAgent.
- dbt adapters: `dbt-postgres`, `dbt-redshift`, `dbt-snowflake` (existing).

**Storage**: Ephemeral only.
- AgentCore Memory (30-day retention) keyed on per-tab session UUID — no schema change.
- Local filesystem `dbt_output/<project>/` in developer mode only.
- Deployed mode: no server-side persistence of generated artifacts; in-memory zip streamed to browser then discarded.

**Testing**: `pytest` for backend (Article IX); `vitest` for frontend (already configured in DSA `package.json`). New contract tests validate SSE event shapes (Pydantic → OpenAPI-style JSON Schema) and the step-scoped prompt routing.

**Target Platform**:
- Production: existing AWS AgentCore Runtime (arm64 Docker) behind AgentCore Gateway, with Amplify-hosted React SPA.
- Local developer: `docker-compose up` (agent container + Vite dev server) pointing at `scripts/bootstrap.sh`-provisioned RDS / Redshift / Snowflake.

**Project Type**: Web application (frontend + Python backend; matches template Option 2).

**Performance Goals**:
- SC-004: Step 1 schema-grounded content visible ≤30s after DB connect (normal network).
- SC-009: Error surface ≤5s after failure detection.
- SC-010: 10 concurrent users with ≤25% per-user latency degradation.
- SC-011: ≥95% refresh-restore success when Memory healthy.

**Constraints**:
- FR-019 forbids new Terraform modules (existing module updates allowed).
- FR-022 forbids downtime during rollout — existing Runtime/Gateway/Memory must keep serving.
- Credentials live only in the active browser session's JS memory; no localStorage, no Secrets Manager.
- dbt artifacts in deployed mode are ephemeral — no bucket, no object, no database row.
- Agent personas are step-scoped per Article VI — no cross-step context bleed; each DSA step uses its own system prompt.
- Dark mode default (Article V); phData palette enforced across new UI.

**Scale/Scope**:
- 3 source database types (PostgreSQL, Redshift, Snowflake).
- 4 workflow steps × 4 theme presets × 2 modes (local / deployed) × 2 operational modes (live / demo).
- 1 backend agent factory reused across all 4 steps with per-step prompts.
- Target ~300 lines in the rewritten `useAgent.ts` (from DSA branch baseline) + ~400 lines of new backend wiring.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Constitution version evaluated: **2.2.0** (2026-04-17). Review covers every article and addendum.

| Article / Addendum | Applies? | Status | Notes |
|---|---|---|---|
| I — Language & uv | ✅ | PASS | Backend stays Python 3.12 + uv. No non-Python backend introduced. No pip/poetry/conda. `uv.lock` committed. |
| II — Frontend stack | ✅ | PASS | React 18 + TypeScript strict + Vite + Tailwind, already in DSA. DSA's `claude.ts` (direct Anthropic SDK) is REMOVED — all LLM calls go through the PlatformAgent backend, honoring "Claude API calls MUST never be made directly from the browser." |
| III — Python best practices | ✅ | PASS with actions | Type hints everywhere, Pydantic for all boundary data (new: `StepRequest`, `StepResponse`, `HeartbeatEvent`, `SessionContext`), `pathlib` only, `logging` not `print`, no mutable defaults. `mypy --strict` MUST pass on new code. Tracking item: existing code not yet fully strict — new code is gated at strict from day one; retrofit is out of scope for this feature. |
| IV — AI/LLM stack | ✅ | PASS | Strands Agents SDK + Bedrock (Sonnet 4 default, Opus 4 for complex tasks). Per-step system prompts live under `src/platform_agent/prompts/steps/` in dedicated files — no inline strings. `anthropic.APIError` handling stays where Anthropic SDK is used (not in this feature's path — we go via Bedrock). |
| V — Design & brand | ✅ | PASS with actions | DSA ships Sana / phData / Dark / Minimal presets; Dark is the default-loaded theme (required). phData palette is already the phData preset's base. Backend-mode indicator (local / deployed) and demo-mode indicator satisfy "backend mode MUST be visible." Panel widths stay DSA-defined (layout stability). Empty states (FR-023) already meaningful in the template. |
| VI — Agent & conversational UX | ✅ | PASS (design-critical) | **One question at a time** enforced at the step-prompt level (system prompts constrain agent output). **Artifact is truth** preserved by DSA — artifact panels are the canonical render; chat is dialog only. **Gates are deliberate** — existing `GateApproval.tsx` stays. **Personas step-scoped** — each of the 4 steps loads its own system prompt + tool allowlist (implemented in Phase 1 design). **No speculation beyond current step** — prompts explicitly forbid cross-step references. |
| VII — Code quality | ✅ | PASS | Separation: backend/frontend/agents/tools dirs already distinct. One tool per file. Mock data under `frontend/src/data/mock/` is already realistic (Atlan, Snowflake, Highspot, data-products). All new async paths wrap in try/except. |
| VIII — Demo & delivery | ✅ | PASS with actions | Scripted demo moment = Northwinds PostgreSQL walkthrough (User Story 1). Loading/error states covered by FR-023 + SC-009. `PLAN.md` exists at root (needs refresh for combined repo — listed as a plan task). `README.md` MUST document `uv`-based setup + `.env.example` + 3-sentence blurb — listed as a plan task. |
| IX — Testing | ✅ | PASS | `pytest` backend; contract tests for SSE schema; `vitest` frontend for `useAgent` step routing and keepalive handling. Unit tests not required for demo-scoped MVPs (Article IX exception) but contract + integration paths MUST be covered. |
| X — Scope discipline | ✅ | PASS | Plan implements only what the spec requires. No refactor of the 5-agent snow-iceberg patterns. No multi-user enterprise features. No credential-storage path. |
| Addendum A — DatabaseDriver protocol | ✅ | PASS | All database access remains routed through `src/platform_agent/drivers/`. No direct connector imports in new code. |
| Addendum B — Kimball methodology | ✅ | PASS | Existing dbt generation honors this; no new modeling code in this feature. |
| Addendum C — Agent guardrails | ✅ | PASS | Agent stays read-only by default; write operations (DDL, dbt materialization) require explicit human approval (wired to the Step 4 gate). DROP/TRUNCATE/ALTER on sources blocked. Session scoped to a single DB per the per-tab sessionStorage ID (D6) — aligns with "Each session is scoped to a single database or catalog." |
| Addendum D — IaC | ✅ | PASS | FR-019 forbids new Terraform modules. Existing modules get small edits (env vars for session-ID propagation, possibly a new Cognito attribute). No console changes. |
| Addendum E — Observability + ADRs in-flight | ✅ | PASS (active) | ADR-015 seeded with D1–D7 during `/speckit.clarify`. This plan phase will extend ADR-015 with design decisions (backend entry shape, heartbeat mechanism, zip-over-SSE protocol, demo-mode architecture) in the same commit that lands the plan. |

**Verdict**: No violations, no justified exceptions — Complexity Tracking table is intentionally empty.

## Project Structure

### Documentation (this feature)

```text
specs/001-dsa-agent-integration/
├── spec.md                  # /speckit.specify output, clarified via /speckit.clarify
├── plan.md                  # This file
├── research.md              # Phase 0 output (this run)
├── data-model.md            # Phase 1 output (this run)
├── quickstart.md            # Phase 1 output (this run)
├── contracts/               # Phase 1 output (this run)
│   ├── sse-events.md        # SSE event schemas (heartbeat, step progress, artifact)
│   ├── http-endpoints.md    # FastAPI endpoints exposed by the backend
│   └── session-header.md    # Session-ID propagation contract
├── checklists/
│   └── requirements.md      # Spec quality checklist (completed)
└── tasks.md                 # Phase 2 output — NOT created by /speckit.plan
```

### Source Code (repository root)

The combined repo already has the dual-root layout required by a web application (Option 2 in the template). The feature slots into that layout without new top-level directories:

```text
dsa-platform/
├── frontend/                              # DSA-imported React app (this feature replaces scaffold)
│   ├── src/
│   │   ├── App.tsx                        # DSA shell
│   │   ├── main.tsx                       # DSA entry
│   │   ├── hooks/
│   │   │   └── useAgent.ts                # REWRITTEN — calls backend via agentcore-client
│   │   ├── context/
│   │   │   ├── AppContext.tsx             # EXTENDED — db-connection state, session ID, demo-mode
│   │   │   └── ThemeContext.tsx           # PRESERVED from DSA
│   │   ├── components/                    # DSA components (shell, chat, artifact, gates)
│   │   ├── lib/
│   │   │   ├── agentcore-client/          # PRESERVED from PlatformAgent (SSE parsers)
│   │   │   ├── auth.ts                    # PRESERVED from PlatformAgent (Cognito PKCE)
│   │   │   ├── session.ts                 # NEW — sessionStorage UUID mint + retrieval
│   │   │   ├── demoMode.ts                # NEW — demo-mode fallback + mock-data loader
│   │   │   ├── types.ts                   # MERGED — DSA + PlatformAgent response types
│   │   │   ├── theme-config.ts            # PRESERVED from DSA
│   │   │   ├── scoring.ts, validation.ts, # PRESERVED from DSA
│   │   │   └── ...                        # (claude.ts DELETED)
│   │   └── data/                          # PRESERVED from DSA (prompts, standards, mock)
│   ├── package.json                       # MERGED — DSA deps + aws-amplify
│   ├── vite.config.ts                     # DSA version
│   └── tsconfig.json                      # DSA version (strict)
├── src/platform_agent/                    # Backend (unchanged core)
│   ├── agent.py                           # Strands agent factory (EXTENDED — accept step_id)
│   ├── models.py                          # Bedrock model config
│   ├── serve.py                           # Legacy AG-UI adapter (UNCHANGED)
│   ├── api/                               # NEW — thin FastAPI sidecar in front of BedrockAgentCoreApp
│   │   ├── __init__.py
│   │   ├── app.py                         # FastAPI app + CORS
│   │   ├── routes_workflow.py             # POST /workflow/step, GET /workflow/artifact/{id}
│   │   ├── routes_health.py               # GET /health
│   │   ├── sse.py                         # SSE event generator + heartbeat emitter
│   │   ├── zip_stream.py                  # In-memory zip response generator
│   │   └── deps.py                        # Session-ID dependency, JWT extraction
│   ├── workflow/                          # NEW — step-scoped orchestration
│   │   ├── __init__.py
│   │   ├── steps.py                       # Step enum + StepConfig registry
│   │   ├── step_1_requirements.py         # Tool allowlist + output contract for Step 1
│   │   ├── step_2_conceptual.py           # Step 2
│   │   ├── step_3_logical.py              # Step 3
│   │   └── step_4_detailed.py             # Step 4 (zip assembly)
│   ├── prompts/
│   │   ├── system.py                      # Existing shared prompt (UNCHANGED)
│   │   └── steps/                         # NEW — per-step system prompts (Article VI)
│   │       ├── step_1_requirements.md
│   │       ├── step_2_conceptual.md
│   │       ├── step_3_logical.md
│   │       └── step_4_detailed.md
│   ├── drivers/                           # UNCHANGED (PostgreSQL, Redshift, Snowflake)
│   ├── tools/                             # UNCHANGED (7 @tool functions)
│   └── session/                           # NEW — Memory key derivation from session ID
│       ├── __init__.py
│       └── memory_adapter.py              # Wraps AgentCore Memory with session-ID key
├── patterns/                              # UNCHANGED (single-agent + 5 snow-iceberg patterns)
├── gateway/                               # UNCHANGED (5 data tools + snowflake/iceberg tools + MCP)
├── infra-terraform/                       # Minor edits only (SSM params for new API, CORS)
│   └── modules/backend/
│       ├── runtime.tf                     # MAYBE EDIT — env vars for new api/ path
│       └── ssm.tf                         # MAYBE EDIT — session-header name parameter
├── streamlit_app/                         # UNCHANGED
├── scripts/                               # UNCHANGED (bootstrap, teardown)
├── eval/                                  # UNCHANGED
├── dbt_output/                            # UNCHANGED
├── docs/
│   ├── adr/015-dsa-agent-integration.md   # EXTENDED during plan phase (D8–D13)
│   └── ...                                # UNCHANGED
├── docker/
│   └── docker-compose.yml                 # UPDATED — frontend dev server + backend api/
├── tests/
│   ├── contract/                          # NEW — SSE schema, session header, step routing
│   │   ├── test_sse_events.py
│   │   ├── test_step_routing.py
│   │   └── test_session_header.py
│   ├── integration/                       # NEW — end-to-end per-step against Northwinds
│   │   ├── test_step_1_postgresql.py
│   │   ├── test_step_2_fk_graph.py
│   │   ├── test_step_3_sample.py
│   │   ├── test_step_4_zip.py
│   │   └── test_keepalive_timeout.py
│   └── unit/                              # Existing + new backend units (workflow, sse, zip_stream)
├── CLAUDE.md                              # UPDATED — reflect combined repo (plan task)
├── PLAN.md                                # UPDATED — combined-repo build order (plan task)
├── README.md                              # UPDATED — combined-repo setup (plan task)
├── pyproject.toml                         # UPDATED — add fastapi, aiofiles (zip stream)
└── .env.example                           # UPDATED — new vars (API_PORT, SESSION_HEADER_NAME)
```

**Structure Decision**: **Option 2 — Web Application.** Dual-root layout already in the combined repo. This feature keeps the existing roots (`frontend/`, `src/platform_agent/`, `patterns/`, `gateway/`, `infra-terraform/`) and adds two new internal subpackages within the Python backend: `src/platform_agent/api/` (thin FastAPI SSE wrapper) and `src/platform_agent/workflow/` (step-scoped orchestration). New files are constrained to these subpackages plus `frontend/src/lib/session.ts` and `frontend/src/lib/demoMode.ts`. No new top-level directories, no new Terraform modules.

## Complexity Tracking

> No Constitution Check violations. This table intentionally left empty.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| *(none)*  | *(none)*   | *(none)*                             |
