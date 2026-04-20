# Contract: SSE Event Schema v1

**Owner**: `src/platform_agent/api/events.py` (Pydantic models) + `src/platform_agent/api/sse.py` (emitter).
**Frontend consumer**: `frontend/src/lib/agentcore-client/parsers/` (version-gated parsers).
**Schema version**: `v = 1` on every event's `data`.
**Framing**: standard SSE — `event: <name>\ndata: <json>\n\n`.

---

## Event reference

### 1. `heartbeat`

**When**: every 10 seconds of idle (no other events emitted) for the duration of the open stream. Also emitted immediately after connection open so the client's silence timer starts from a known baseline.

**data**:
```json
{ "v": 1, "t": "2026-04-17T15:03:01Z" }
```

**Client behavior**: reset the 30-second silence timer. Do not render in chat.

---

### 2. `tool_start`

**When**: the Strands agent invokes a `@tool` function.

**data**:
```json
{
  "v": 1,
  "run_id": "6f0a...c2",
  "tool": "scan_metadata",
  "args_summary": "schema=public",
  "t": "2026-04-17T15:03:05Z"
}
```

**Rules**:
- `args_summary` MUST NOT include credentials or query bodies exceeding 200 chars.
- `run_id` is identical across every event in a single `POST /workflow/step` stream; it's the cancel key.

**Client behavior**: append a "Running <tool>…" line to the progress pane.

---

### 3. `tool_progress`

**When**: a long-running tool emits progress at a natural boundary.

**data**:
```json
{
  "v": 1,
  "run_id": "6f0a...c2",
  "tool": "scan_metadata",
  "index": 4,
  "total": 14,
  "note": "profiling table orders",
  "t": "2026-04-17T15:03:12Z"
}
```

**Rules**:
- `index` and `total` both optional; if `total` is known, frontend renders "4 / 14"; if only `index`, renders "4".
- `note` ≤100 chars.
- Tool MUST emit at least one `tool_progress` event for any operation expected to take >10 seconds (enforced by `@long_running` decorator in tool wrappers).

**Client behavior**: update progress pane; reset silence timer.

---

### 4. `tool_result`

**When**: a `@tool` function returns.

**data**:
```json
{
  "v": 1,
  "run_id": "6f0a...c2",
  "tool": "scan_metadata",
  "summary": "Found 14 tables with 42 foreign keys across 8 entities.",
  "t": "2026-04-17T15:03:18Z"
}
```

**Rules**:
- `summary` is LLM-free human-readable (generated in the tool wrapper, not by the model).
- Raw tool output is NOT shipped — it's too large. Structured data goes in `artifact_update`.

---

### 5. `message`

**When**: Strands streams chat output from Bedrock.

**data**:
```json
{
  "v": 1,
  "run_id": "6f0a...c2",
  "role": "assistant",
  "content": "Based on the schema, I propose the following entities…",
  "delta": true,
  "t": "2026-04-17T15:03:20Z"
}
```

**Rules**:
- `delta: true` means append to the current assistant message; `delta: false` means a full replacement (rare, used for error-correcting regenerations).
- `role` is always `"assistant"` from the server; user messages are request-side only.

**Client behavior**: stream into the chat bubble; update every render tick.

---

### 6. `artifact_update`

**When**: a step-specific artifact is ready (PRD draft, ERD graph, logical-model update, dbt-preview). Multiple updates per step are expected.

**data** (discriminated on `artifact_type`):

PRD (Step 1):
```json
{
  "v": 1, "run_id": "6f0a...c2",
  "step": "requirements",
  "artifact_type": "prd",
  "payload": {
    "sections": [ { "heading": "…", "body": "…", "cited_tables": ["public.orders"], "completeness_contribution": 0.25 } ],
    "completeness": 0.75
  },
  "t": "2026-04-17T15:03:25Z"
}
```

Conceptual model (Step 2):
```json
{
  "v": 1, "run_id": "…",
  "step": "conceptual",
  "artifact_type": "conceptual_model",
  "payload": { "entities": [ … ], "relationships": [ … ] },
  "t": "…"
}
```

Logical model (Step 3):
```json
{
  "v": 1, "run_id": "…",
  "step": "logical",
  "artifact_type": "logical_model",
  "payload": { "tables": [ … ] },
  "t": "…"
}
```

**Rules**:
- Payload shapes match `data-model.md` entities exactly.
- Artifact updates are idempotent — later updates wholly replace earlier ones for the same `step` + `artifact_type` pair.

---

### 7. `artifact_ready` (Step 4 only)

**When**: the zip is buffered and ready for a second HTTP request.

**data**:
```json
{
  "v": 1, "run_id": "6f0a...c2",
  "step": "detailed",
  "handle": "c6a0...ee",
  "size_bytes": 17432,
  "file_count": 23,
  "expires_in_s": 60,
  "download_url": "/workflow/artifact/c6a0...ee",
  "t": "2026-04-17T15:04:00Z"
}
```

**Rules**:
- Exactly zero or one `artifact_ready` per stream; only on successful Step 4.
- Frontend MUST fetch the zip within `expires_in_s`.

**Client behavior**: trigger a browser download of `download_url`. Display a "Download dbt project" button as a secondary UI affordance.

---

### 8. `error`

**When**: anywhere — validation, tool failure, agent failure, cancellation.

**data**:
```json
{
  "v": 1, "run_id": "6f0a...c2",
  "code": "tool_error" | "agent_error" | "cancelled" | "timeout" | "unauthorized" | "validation_error",
  "message": "Human-readable, no stack trace.",
  "retriable": true,
  "t": "2026-04-17T15:03:45Z"
}
```

**Rules**:
- Terminal — server closes stream after sending.
- `retriable: true` means the frontend may offer a "Retry" button; `false` means it should not (unauthorized, validation, cancelled).

**Client behavior**:
- Render a persistent error panel tied to the current step.
- If `retriable`, offer Retry.
- Always offer "Continue in demo mode" (FR-017).

---

### 9. `done`

**When**: a non-Step-4 step completes successfully.

**data**:
```json
{ "v": 1, "run_id": "6f0a...c2", "step": "requirements", "t": "2026-04-17T15:03:30Z" }
```

**Rules**:
- Terminal — server closes stream after sending.
- For Step 4, `artifact_ready` replaces `done` (`done` is NOT also emitted).

---

## Invariants

- Every stream ends with exactly ONE terminal event (`done`, `error`, or `artifact_ready`).
- Events carry UTC ISO 8601 timestamps generated server-side.
- Schema version bump (v2) requires a new parser module and a migration note in ADR-015.

## Contract tests

Live in `tests/contract/test_sse_events.py`:

- Round-trip every Pydantic model → JSON → parser → Pydantic; assert equality.
- Invalid events (missing `v`, unknown `code`, negative `index`) raise parser errors.
- A stream without a terminal event times out and is flagged.
- A stream emitting `done` followed by `message` raises "event after terminal" error.
- Heartbeat cadence: simulate 25s of no activity; observe ≥2 `heartbeat` events.
