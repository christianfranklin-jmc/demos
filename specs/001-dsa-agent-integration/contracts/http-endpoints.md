# Contract: HTTP Endpoints

**Owner**: `src/platform_agent/api/app.py` and child routers.
**Transport**: HTTP/1.1 over TLS in deployed mode (Gateway terminates TLS); HTTP/1.1 in local Docker Compose.
**CORS**: Allowed origins = `http://localhost:5173` (Vite dev) and the Amplify app URL. Allowed headers include `X-DSA-Session-ID` and `Authorization`. Credentials: `omit` (no cookies).

All request/response bodies are JSON unless explicitly noted. All responses carry `Cache-Control: no-store`.

---

## `GET /health`

Liveness probe. No authentication. No session.

**Response 200**:
```json
{ "status": "ok", "build": "<git-sha>", "mode": "local" | "deployed" }
```

**Contract test**: returns 200 within 250ms; `status == "ok"`.

---

## `POST /workflow/step`

The primary workflow entry point. The frontend POSTs once per user turn; the server responds with a long-lived SSE stream (see contracts/sse-events.md).

**Authentication**: `Authorization: Bearer <JWT>` in deployed mode (required). Absent in local mode (container runs without Cognito).

**Required headers**:
| Header | Value |
|---|---|
| `Content-Type` | `application/json` |
| `Accept` | `text/event-stream` |
| `X-DSA-Session-ID` | UUIDv4, minted by frontend on tab mount |

**Request body** — `StepRequest` (see data-model.md §3):
```json
{
  "step_id": "requirements",
  "user_message": "We want to understand our order data.",
  "prior_artifact": null,
  "connection": {
    "driver_type": "postgresql",
    "host": "...", "port": 5432, "database": "northwinds",
    "schema": "public", "user": "postgres",
    "credential": { "kind": "password", "password": "…" }
  },
  "resume": false
}
```

**Response 200** — `Content-Type: text/event-stream`:
A stream of SSE frames per contracts/sse-events.md. Connection stays open until a terminal `done`, `error`, or `artifact_ready` event is sent, then the server closes.

**Response 400** — validation failure (bad step_id, missing connection when step requires one, prior_artifact type mismatch). Body:
```json
{ "error": { "code": "validation_error", "message": "…", "field": "connection" } }
```

**Response 401** — missing/invalid JWT in deployed mode. Body empty.

**Response 409** — session-ID collision (extremely rare; session exists and is currently being used by a different user_scope). Body:
```json
{ "error": { "code": "session_conflict", "message": "Session ID is in use by another identity." } }
```

**Response 429** — rate limit hit. Deployed mode only, enforced by AgentCore Gateway. Body:
```json
{ "error": { "code": "rate_limited", "retry_after_s": 30 } }
```

**Response 500** — unhandled backend error. Body redacts stack; logs carry trace ID (returned as `X-Trace-Id` header).

**Contract tests** (`tests/contract/test_step_routing.py`):
- Given a valid `REQUIREMENTS` request without a connection, server returns 400 citing `connection`.
- Given a valid request, server begins streaming within 500ms (first event MUST be `heartbeat` or `tool_start`).
- Given `resume: true` with a known session, first SSE event references prior history.

---

## `GET /workflow/artifact/{handle}`

Download the Step 4 dbt zip produced by a prior `POST /workflow/step` that emitted an `artifact_ready` event.

**Authentication**: same as `POST /workflow/step`.

**Required headers**: `X-DSA-Session-ID` matching the session that produced the handle (defense-in-depth; the handle is random and single-use, but we also bind it).

**Path param**: `handle` — UUIDv4 from the prior `artifact_ready` event.

**Response 200**:
- `Content-Type: application/zip`
- `Content-Disposition: attachment; filename="<project_name>-<timestamp>.zip"`
- Body: streamed zip of the generated dbt project + semantic layer YAML.
- On success, the server atomically drops the handle from its in-memory store (single-use).

**Response 404** — handle unknown, expired, or already consumed. Body empty.

**Response 403** — session-ID mismatch (different session than the one that produced the handle). Body empty.

**Contract tests** (`tests/contract/test_step_routing.py`):
- Zip is valid (`zipfile.is_zipfile` + `.testzip()` returns None on the downloaded bytes).
- Second GET to the same handle returns 404.
- GET from a different session-ID returns 403.
- Handle created >60s ago returns 404 even before any GET.

---

## `POST /workflow/cancel`

Abort an in-progress `POST /workflow/step` stream. Emitted when the user clicks the Cancel button.

**Request body**:
```json
{ "session_id": "…", "run_id": "…" }
```

Where `run_id` is the UUID embedded in the current stream's first event (`tool_start.run_id`).

**Response 200**: `{ "cancelled": true }` when the run was found and cancellation was propagated. `{ "cancelled": false }` if the run had already completed.

**Contract test**: mid-stream cancel causes the open SSE stream to emit a final `error` event with `code: "cancelled"` and close within 1 second.

---

## Out of scope for this feature

Explicitly NOT provided by the backend:
- `GET /workflow/sessions` (list) — deferred; demos do not browse history.
- `POST /workflow/session/resume` — resume is handled inline via `StepRequest.resume` flag.
- `GET /workflow/artifact/{handle}/metadata` — metadata ships in the `artifact_ready` SSE event.
