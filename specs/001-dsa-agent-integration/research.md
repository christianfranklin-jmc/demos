# Phase 0 Research: DSA × PlatformAgent Integration

**Branch**: `001-dsa-agent-integration` | **Date**: 2026-04-17

This document resolves open technical questions identified during plan drafting so that Phase 1 design and Phase 2 task breakdown can proceed without re-litigating architecture choices. Each section follows the format **Decision / Rationale / Alternatives considered**. Decisions here amend ADR-015.

---

## R1. Backend entry point exposing the DSA frontend

**Decision**: Run a thin **FastAPI** app (`src/platform_agent/api/app.py`) in the same container as the existing `BedrockAgentCoreApp`. The FastAPI app owns HTTP routing, SSE streaming, session-ID extraction, and zip-response generation. It invokes the Strands agent factory (`create_agent(step_id, session_ctx)`) internally rather than calling the agent over the wire. The existing `serve.py` AG-UI adapter stays in place for legacy flows (unchanged). AgentCore Gateway + Runtime continue to front the container; Gateway routes HTTP into FastAPI and also exposes the existing Lambda tool targets unchanged.

**Rationale**:
- **Control over SSE event format.** DSA's `useAgent` needs a predictable stream of `{event, data}` lines for progress, heartbeat, artifact, and error. AG-UI's pre-canned event types are looser than what we need for step-scoped orchestration.
- **Zip-over-HTTP is a first-class FastAPI capability** (`StreamingResponse`); bolting it onto the AG-UI protocol would be awkward.
- **Keepalive heartbeats** are easier to emit from an async FastAPI generator than from AG-UI's existing event loop.
- Constitution Article I allows FastAPI (`fastapi` is the default recommendation in Article III's project structure).
- Keeps `serve.py` alive so existing integration tests and Streamlit sanity checks do not regress.
- Single container = no new Terraform module (FR-019 honored).

**Alternatives considered**:
- **Reuse `serve.py` AG-UI adapter.** Rejected — forces us to map custom step/heartbeat/zip behavior onto AG-UI event types that do not match the DSA use case. Rework effort exceeds FastAPI layer cost.
- **New `patterns/dsa-workflow/` BedrockAgentCoreApp.** Rejected — would duplicate much of the existing `patterns/platform-agent/` wiring, increasing maintenance surface for no benefit beyond the FastAPI option.
- **Lambda-backed API Gateway in front of the Strands agent.** Rejected — adds cold-start latency, a new Terraform module, and complicates session continuity. Violates FR-019.

**Implications for design**: See contracts/http-endpoints.md for routes. FastAPI must be added to `pyproject.toml`. The Docker `CMD` becomes `uvicorn platform_agent.api.app:app` (replacing the legacy entry) or a small supervisor that runs both (simpler: FastAPI only, since `BedrockAgentCoreApp` becomes an in-process library).

**ADR-015 amendment**: D8 (FastAPI sidecar).

---

## R2. Keepalive heartbeat emission during long tool calls

**Decision**: Implement heartbeats at **two layers**: (a) FastAPI SSE generator emits a `heartbeat` event every 10 seconds of idle (no tool output) as a safety net; (b) Strands tool wrappers opt into a `yield_heartbeat()` callback that long-running tools (`scan_metadata`, `profile_database`, `generate_dbt_project`) invoke at natural progress boundaries (per-schema, per-table, per-model). The frontend's silence timer is reset by either event type. 30 seconds of silence triggers failure per spec FR-023.

**Rationale**:
- **Two layers cover two failure modes.** The per-tool callback keeps heartbeats meaningful (they represent actual progress). The SSE generator's passive 10s emitter ensures even a stuck tool call still emits something before the frontend's 30s timeout — giving a 20-second grace period for the agent to recover or for the user to cancel.
- **Natural progress boundaries** (one heartbeat per table discovered, per column profiled) double as useful UX — the progress pane can render "Scanning table 4 of 14".
- 10 seconds idle → 3 heartbeats within the frontend's 30s window. Redundant enough to survive a single lost packet.
- No Strands core modifications — heartbeats ride on existing tool instrumentation.

**Alternatives considered**:
- **Single passive emitter only, no per-tool hooks.** Rejected — the user sees "thinking…" with no progress detail, contradicting FR-023 ("MUST surface agent progress … incrementally").
- **Per-tool hooks only, no passive emitter.** Rejected — a tool that crashes partway through its loop stops emitting entirely; the frontend waits the full 30s before falling back.
- **Increase frontend timeout to 60s.** Rejected — directly contradicts the clarified spec (FR-023 + Q5).

**Implications for design**: `src/platform_agent/api/sse.py` owns the passive emitter. Tool modules import a `heartbeat_emitter` dependency and call it at progress boundaries. The frontend resets its silence timer on every event, regardless of type.

**ADR-015 amendment**: D9 (dual-layer heartbeat).

---

## R3. Delivering the dbt zip in deployed mode

**Decision**: Step 4 is a **two-phase** interaction. Phase 1: the agent runs `generate_dbt_project` + `generate_semantic_layer` and emits an `artifact_ready` SSE event containing a short-lived handle (UUID) and metadata (file count, size). The backend stores the generated file tree **in the request-scoped task's memory** (a Python object living only for the duration of the open SSE generator). Phase 2: the frontend, upon receiving `artifact_ready`, issues a second HTTP request `GET /workflow/artifact/{handle}` to the same FastAPI app; the response is a streamed zip (`Content-Type: application/zip`, `Content-Disposition: attachment`). The handle is single-use and expires after 60 seconds or on server restart.

**Rationale**:
- **Streaming a zip over SSE is illegal** (SSE is text-framed). We need a second HTTP channel for binary payload.
- **Request-scoped memory** avoids FR-019's "no new Terraform modules" constraint (no S3 bucket). The handle is only valid as long as the container process lives — matches "server MUST NOT persist generated artifacts beyond the life of the request" (FR-008 clarified).
- **Short TTL (60s) + single-use** prevents accidental replay or inter-user leakage even on a shared container.
- **Browser download UX** uses a standard `<a download>` link driven by a blob URL constructed from the response, which is what DSA's existing artifact panel already handles in demo mode.

**Alternatives considered**:
- **Base64-encode the zip in an SSE event.** Rejected — massive transport overhead (>33% bloat), awkward to reconstruct binary from SSE text, and a 2 MB dbt project becomes 2.7 MB of SSE events that the parser must buffer.
- **Separate WebSocket channel for binary.** Rejected — adds a protocol, needs CORS/auth parity, and WebSocket upgrade behind AgentCore Gateway is untested.
- **Inline the files as JSON in the final SSE event.** Rejected — bypasses "browser file download" UX; user would need a "Save As" flow per file.

**Implications for design**: `src/platform_agent/api/zip_stream.py` builds zip in memory (`zipfile.ZipFile` with `io.BytesIO` buffer) and returns it via FastAPI `StreamingResponse`. Handle store is a plain `dict[str, tuple[bytes, datetime]]` with a sweep task (every 60s, drop expired). For concurrency correctness the dict lives on `app.state` and is guarded by an `asyncio.Lock`.

**ADR-015 amendment**: D10 (two-phase zip delivery).

---

## R4. Session-ID propagation from frontend to AgentCore Memory

**Decision**: The frontend mints a UUIDv4 on first mount and stores it in `sessionStorage["dsa_session_id"]`. Every agent request sends the ID in an HTTP header **`X-DSA-Session-ID`**. FastAPI's `deps.py` extracts the header into a typed `SessionContext` Pydantic model that is passed to the Strands agent factory. The Memory adapter derives its memory key as `f"dsa:{cognito_sub or 'local'}:{session_id}"`, ensuring even two authenticated users with a colliding session UUID (astronomically unlikely, but technically possible) remain isolated.

**Rationale**:
- **Header vs cookie**: headers do not persist across unrelated navigations and survive CORS preflight cleanly — right tool for the job.
- **Custom header `X-DSA-Session-ID`** follows the `X-` convention for non-standard headers; the name is explicit and searchable in CloudWatch logs.
- **User-scoped prefix** (`cognito_sub`) adds defense-in-depth against session-ID collision or forgery; also makes CloudWatch log filtering by user trivial.
- **Pydantic `SessionContext`** gives us strict typing into the agent factory, matching Article III's Pydantic-at-boundaries rule.
- **No change to AgentCore Memory configuration** — it already accepts arbitrary keys; we just pass a richer one.

**Alternatives considered**:
- **Stuff the session ID into the JWT as a custom claim.** Rejected — JWT mutation complicates Cognito integration, and the session ID is not identity, it is UX scope. Different concerns.
- **Query-string parameter `?sid=`.** Rejected — leaks into CloudWatch access logs, browser history, and referer headers.
- **Body field on every request.** Rejected — SSE requests are GET-style; bodyless is simpler for streaming endpoints.

**Implications for design**: see contracts/session-header.md for full header spec. The frontend's `session.ts` module handles mint + retrieve + attach. The backend's `deps.py` has a single FastAPI dependency `get_session_context(request: Request) -> SessionContext`.

**ADR-015 amendment**: D11 (session-ID header + Memory key derivation).

---

## R5. DSA import — merge strategy & conflict resolution

**Decision**: Create a temporary working branch `dsa-import-staging` locally, check out `dsa/feat-enhancements-erd-visuals`, relocate DSA's source (`src/` → `frontend/src/`, `package.json` → `frontend/package.json`, docs/index.html/config files) using `git mv`, commit the restructure, then merge that staging branch into `001-dsa-agent-integration` using `--allow-unrelated-histories`. Resolution rules:
- **`frontend/src/lib/claude.ts`** (DSA) — DELETE. All LLM calls route through the backend.
- **`frontend/src/lib/agentcore-client/`** (PlatformAgent) — KEEP; do not overwrite with DSA's empty slot.
- **`frontend/src/lib/auth.ts`** (PlatformAgent) — KEEP; DSA has no equivalent.
- **`frontend/src/App.tsx`, `main.tsx`, `hooks/`, `context/`, `components/`, `data/`** — USE DSA; PlatformAgent's basic scaffold is replaced wholesale.
- **`frontend/package.json`** — MERGE: DSA deps base + `aws-amplify@^6` from PlatformAgent.
- **`frontend/vite.config.ts`, `tsconfig.json`** — USE DSA.
- **`frontend/index.html`** — USE DSA.
- **`frontend/tailwind.config.*`, `postcss.config.*`** — USE DSA (Tailwind v4 already).

**Rationale**:
- Staging branch isolates the noisy restructure commit from the merge commit, making the feature-branch history readable.
- Explicit per-file rules mean the human resolving conflicts never guesses — the spec and ADR have already decided.
- `--allow-unrelated-histories` is correct for this merge since `dsa-mvp` and `PlatformAgent_1` have no common ancestor.

**Alternatives considered**:
- **`git subtree add`** into `frontend/`. Rejected — subtree commits complicate future rebases and most of DSA's `docs/` should go to the repo root, not `frontend/docs/`.
- **Manual file copy (no git history).** Rejected — loses DSA's commit attribution and makes `git blame` useless in `frontend/src/`.
- **Merge DSA branch directly without restructure.** Rejected — leaves DSA's `src/` at the repo root, colliding with `src/platform_agent/`.

**Implications for design**: plan task T-IMPORT-01 ("Import DSA feat-enhancements-erd-visuals via staging branch") will execute this. Post-merge, `claude.ts` deletion is a separate commit so the removal is visible in history.

**ADR-015 amendment**: none needed (decision is process/mechanical; captured in this research doc and will appear in tasks.md).

---

## R6. Per-step system prompt loading

**Decision**: Store each step's system prompt as a separate Markdown file under `src/platform_agent/prompts/steps/` (one per step: `step_1_requirements.md`, `step_2_conceptual.md`, `step_3_logical.md`, `step_4_detailed.md`). The `create_agent()` factory accepts a `step_id: StepId` parameter, loads the file via `pathlib.Path(...).read_text()`, and injects it as the Strands agent's system prompt. A `StepConfig` Pydantic model per step declares:
- `step_id`
- `system_prompt_path`
- `allowed_tools` (subset of the 7 agent tools)
- `require_db_connection` (bool)
- `output_contract` (which SSE artifact events are expected to fire)

**Rationale**:
- **Article IV**: "System prompts live in dedicated files … never inline strings." Markdown files satisfy this directly.
- **Article VI "Personas step-scoped"**: tool allowlist per step prevents cross-step drift (Step 1 cannot reach `generate_dbt_project`; Step 4 cannot arbitrarily re-scan schema without the user's gate approval).
- **Pydantic `StepConfig`** boundary enforces Article III's "no raw dicts as function contracts."
- Decoupling the prompt from code means non-engineers can iterate on prompt wording without Python knowledge.

**Alternatives considered**:
- **Single shared prompt with step header tags.** Rejected — violates Article VI's persona scoping; harder to A/B test individual step prompts.
- **Prompts in Python constants.** Rejected — Article IV forbids inline strings.
- **Prompts in Memory records.** Rejected — introduces write dependency on Memory for startup; adds operational complexity for no gain.

**Implications for design**: see `workflow/steps.py` + `workflow/step_N_*.py`. `StepConfig` registry is a module-level `dict[StepId, StepConfig]`.

**ADR-015 amendment**: D12 (step-scoped prompts + tool allowlist).

---

## R7. Demo-mode toggling architecture

**Decision**: Demo mode is **purely a frontend concern**. When demo mode is active (toggled in the UI, or auto-activated after a failed live call per FR-017), `useAgent.ts` short-circuits: instead of calling `agentcore-client`, it invokes `demoMode.resolveStep(stepId, userInput)` which returns mock responses synthesised from bundled datasets under `frontend/src/data/mock/`. The backend never knows demo mode exists. A global `demoMode: boolean` + `demoModeReason: 'user_toggle' | 'auto_fallback'` lives in `AppContext`. All demo-mode artifacts render with a corner watermark badge driven by a `<DemoBadge>` component visible on every artifact panel.

**Rationale**:
- **Zero backend coupling** means demo mode survives even when the backend is entirely unreachable (the core point of demo mode).
- **No demo-mode flag in the wire protocol** means no risk of a "demo=true" leaking into production analytics or traces.
- **Auto-fallback** is a pure UX decision handled at the error boundary — no backend knowledge required.
- Reusing existing `frontend/src/data/mock/` datasets (Atlan, Snowflake, Highspot, data-products) means the content is already realistic per Article VII.

**Alternatives considered**:
- **Backend `/workflow/step?mode=demo`** endpoint. Rejected — breaks "zero backend dep" (demo mode dies when backend dies). Violates purpose.
- **Mock backend service in Docker Compose.** Rejected — doubles demo surface (what counts as "the demo"?). Adds a moving part.
- **Top-of-screen banner only (no per-artifact badge).** Rejected — FR-018 requires the user cannot mistake demo output for real; a persistent per-artifact badge is the minimum.

**Implications for design**: `frontend/src/lib/demoMode.ts` owns the mock dispatcher. `<DemoBadge>` lives in `frontend/src/components/shared/DemoBadge.tsx`. `useAgent` branches on `demoMode` at the top of each step handler.

**ADR-015 amendment**: D13 (frontend-only demo mode).

---

## R8. SSE event schema (per-step progress, heartbeat, artifact, error)

**Decision**: A closed set of event types, all JSON-encoded in the SSE `data:` field, with a version field for forward-compat. Types:

| `event` | `data` shape | Emitted by | When |
|---|---|---|---|
| `heartbeat` | `{ t: ISO8601 }` | passive SSE emitter | every 10s idle |
| `tool_start` | `{ tool, args_summary, t }` | Strands tool wrapper | when a `@tool` fn begins |
| `tool_progress` | `{ tool, index, total?, note, t }` | tool body callback | at natural progress points |
| `tool_result` | `{ tool, summary, t }` | Strands tool wrapper | when a `@tool` fn returns |
| `message` | `{ role, content, t }` | Strands agent loop | chat output token/chunk |
| `artifact_update` | `{ step, artifact_type, payload, t }` | step handler | when a step-specific artifact is ready (e.g., PRD draft, ERD graph, logical-model table, dbt-preview) |
| `artifact_ready` | `{ step, handle, size_bytes, file_count, expires_in_s, t }` | step 4 handler | when zip is buffered and downloadable |
| `error` | `{ code, message, retriable, t }` | any path | on failure |
| `done` | `{ step, t }` | step handler | when step completes successfully |

All shapes are Pydantic models under `src/platform_agent/api/events.py`. Frontend parsers live under `frontend/src/lib/agentcore-client/parsers/` and are version-gated.

**Rationale**:
- **Closed event set** keeps the frontend parser exhaustive — easy to detect unknown event types.
- **Version field** (via `data.v = 1`) lets us evolve without breaking deployed clients.
- **`tool_progress.index/total`** drives the "Scanning table 4 of 14" UX affordance.
- **`artifact_update` vs `artifact_ready`**: updates are incremental renders (ERD nodes arriving); ready is the terminal download signal.
- Pydantic at the boundary satisfies Article III.

**Alternatives considered**:
- **Free-form `data` JSON.** Rejected — no type safety, frontend parsers become defensive soup.
- **OpenAI-style `delta` events.** Rejected — too specific to token streaming; we need higher-level step events.
- **ProtocolBuffers over SSE.** Rejected — adds codegen toolchain for negligible payload savings at this scale.

**Implications for design**: see contracts/sse-events.md for canonical schema. Contract tests verify every Pydantic model round-trips through the SSE parser.

**ADR-015 amendment**: D14 (SSE event schema v1).

---

## Summary

All plan-level "NEEDS CLARIFICATION" items resolved. No outstanding unknowns block Phase 1. ADR-015 will be extended with D8–D14 in the same commit that lands this plan.
