# Phase 1 Data Model: DSA × PlatformAgent Integration

**Branch**: `001-dsa-agent-integration` | **Date**: 2026-04-17

This document defines the Pydantic models (backend) and TypeScript interfaces (frontend) that carry state across the feature's internal and external boundaries. All Python models use Pydantic v2 per Constitution Article III. All TypeScript types use strict mode. Validation rules derive directly from the spec's FRs and clarified answers.

## Conventions

- Python models: `src/platform_agent/api/events.py`, `src/platform_agent/workflow/steps.py`, `src/platform_agent/session/memory_adapter.py`. Every model inherits from `pydantic.BaseModel` with `model_config = ConfigDict(extra="forbid")` unless stated otherwise.
- TypeScript types: `frontend/src/lib/types.ts`. Mirror the Python shapes one-for-one.
- Timestamps: ISO 8601 UTC strings. Generated server-side.
- IDs: UUIDv4 strings unless noted.

---

## 1. Session & Identity

### `SessionContext` (Python)

| Field | Type | Source | Validation | Notes |
|---|---|---|---|---|
| `session_id` | `UUID` | Request header `X-DSA-Session-ID` | Must parse as UUIDv4 | Minted by frontend on tab mount; persists in `sessionStorage`. |
| `cognito_sub` | `str \| None` | JWT `sub` claim | Base64URL string | `None` in local mode (no Cognito). |
| `username` | `str \| None` | JWT `email` / `cognito:username` | Email format if present | Used only for trace labels. |
| `mode` | `Literal["local", "deployed"]` | Request origin / env | — | Derived from request host + presence of `Authorization` header. |
| `issued_at` | `datetime` | Server clock | UTC | Set on dependency resolution. |

**Lifecycle**: Constructed on each HTTP request via FastAPI `Depends(get_session_context)`. Never persisted. Never logged in full — `session_id` logged as first 8 chars + `…`.

**Invariant**: In `deployed` mode, `cognito_sub` MUST be non-None (JWT is required). In `local` mode, `cognito_sub` is always `None`.

**Maps to FR**: FR-020, FR-026, FR-027, FR-029.

### `MemoryKey` (Python)

Derived type, never serialized across the wire:

```python
@dataclass(frozen=True)
class MemoryKey:
    prefix: Literal["dsa"]
    user_scope: str   # cognito_sub or "local"
    session_id: str   # str(session.session_id)
    
    def as_string(self) -> str:
        return f"{self.prefix}:{self.user_scope}:{self.session_id}"
```

**Invariant**: Never instantiated outside `session/memory_adapter.py`. Every Memory read/write routes through a single method that derives this from a `SessionContext`.

---

## 2. Workflow Step Configuration

### `StepId` (Python `StrEnum`; TypeScript `"requirements" | "conceptual" | "logical" | "detailed"`)

```python
class StepId(StrEnum):
    REQUIREMENTS = "requirements"
    CONCEPTUAL = "conceptual"
    LOGICAL = "logical"
    DETAILED = "detailed"
```

### `StepConfig` (Python)

| Field | Type | Validation | Notes |
|---|---|---|---|
| `step_id` | `StepId` | — | Primary key in the step registry. |
| `display_order` | `int` | `1..4` | Matches DSA's 4-step UX. |
| `system_prompt_path` | `Path` | File MUST exist on startup | Loaded lazily; cached after first read. |
| `allowed_tools` | `frozenset[str]` | Each member MUST be a registered `@tool` name | Enforces Article VI persona scoping. |
| `require_db_connection` | `bool` | — | Steps 1–4 all require a connection in live mode. |
| `output_contract` | `StepOutputContract` | — | Which SSE artifact events this step is expected to emit (for contract tests). |

**Registry**: `STEP_REGISTRY: dict[StepId, StepConfig]` defined in `workflow/steps.py`.

**Invariant**: `allowed_tools` for each step is a **subset** of the agent's registered tool names; no step may claim a tool that does not exist. Validated on import via a module-level check.

| StepId | allowed_tools |
|---|---|
| REQUIREMENTS | `connect_to_database`, `scan_metadata` |
| CONCEPTUAL | `scan_metadata`, `run_query` (FK inspection only) |
| LOGICAL | `run_query`, `profile_database` |
| DETAILED | `generate_dbt_project`, `generate_semantic_layer` |

**Maps to FR**: FR-005, FR-006, FR-007, FR-008, FR-010; Constitution Article VI.

---

## 3. Workflow Request & Response

### `StepRequest` (Python, TypeScript mirror)

| Field | Type | Validation | Notes |
|---|---|---|---|
| `step_id` | `StepId` | — | Which DSA step is being invoked. |
| `user_message` | `str` | `1..4000` chars | The chat input from the user. |
| `prior_artifact` | `PriorArtifact \| None` | — | Pass-through of the approved artifact(s) from earlier steps. |
| `connection` | `SourceConnection \| None` | Required when step's `require_db_connection` is True | Session-scoped DB credentials. |
| `resume` | `bool` | Default `False` | If True, the server looks up prior conversation by memory key. |

### `PriorArtifact` (Python, TypeScript mirror)

Discriminated union on `artifact_type`:

| `artifact_type` | Payload |
|---|---|
| `"prd"` | `{ sections: list[PrdSection], completeness: float }` |
| `"conceptual_model"` | `{ entities: list[Entity], relationships: list[Relationship] }` |
| `"logical_model"` | `{ tables: list[LogicalTable] }` |

Step N's handler consumes up to Step N-1's artifacts; passing a later one is rejected with a 400.

### `SourceConnection` (Python, TypeScript mirror)

| Field | Type | Validation |
|---|---|---|
| `driver_type` | `Literal["postgresql", "redshift", "snowflake"]` | — |
| `host` or `account` | `str` | Non-empty |
| `port` | `int \| None` | 1..65535 when present |
| `database` | `str` | Non-empty |
| `schema` | `str \| None` | — |
| `user` | `str` | Non-empty |
| `credential` | `Credential` | Discriminated on `kind` |

`Credential = PasswordCredential | SSOExternalBrowserCredential`. SSO variant carries no secret; the backend's driver layer triggers the browser-based OAuth flow.

**Invariant (FR-014 clarified)**: `SourceConnection` MUST never be persisted — it is request-scoped only. Lint rule: no module outside `api/` and `drivers/` may import `SourceConnection`.

**Maps to FR**: FR-011, FR-012, FR-014.

### `StepResponse` (logical) — emitted as a stream of SSE events, not a single object

See `contracts/sse-events.md` for the wire-level schema. Logically a `StepResponse` is the concatenation of:
1. Zero or more `tool_start` / `tool_progress` / `tool_result` events.
2. Zero or more `message` events (streaming chat).
3. Zero or more `artifact_update` events.
4. Exactly one terminal event: `done`, `error`, or `artifact_ready` (step 4 only).

**Maps to FR**: FR-023 (streaming), FR-025 (specific error surface), Clarify Q5 (keepalive).

---

## 4. Domain Entities Rendered by the UI

### `Entity` (Conceptual Model, Step 2)

| Field | Type | Validation | Notes |
|---|---|---|---|
| `id` | `str` | Slug; stable | Derived from source table name. |
| `label` | `str` | Non-empty | Human-facing. |
| `source_table` | `str` | FQN `schema.table` | The real source. |
| `row_count_est` | `int \| None` | >= 0 | From `scan_metadata`. |
| `key_columns` | `list[str]` | Non-empty when PK known | Primary key columns. |

### `Relationship` (Conceptual Model, Step 2)

| Field | Type | Validation | Notes |
|---|---|---|---|
| `from_entity_id` | `str` | Must match an `Entity.id` | — |
| `to_entity_id` | `str` | Must match an `Entity.id` | — |
| `from_column` | `str` | — | FK column on source. |
| `to_column` | `str` | — | Referenced column. |
| `cardinality` | `Literal["1:1", "1:N", "N:1", "N:M"]` | — | Inferred from FK + uniqueness. |

**Derivation rule**: populated from `information_schema.key_column_usage` + `table_constraints` via `scan_metadata`. For Snowflake (which doesn't reliably expose FKs), fall back to naming heuristics + `PRIMARY KEY` metadata, and mark each inferred relationship with `inferred: true` so the UI can render it as a dashed edge.

**Maps to FR**: FR-006.

### `LogicalTable` / `LogicalField` (Logical Model, Step 3)

| Field | Type | Validation | Notes |
|---|---|---|---|
| `table.id` | `str` | — | — |
| `table.label` | `str` | — | — |
| `table.grain` | `str \| None` | — | User-editable; agent proposes. |
| `field.name` | `str` | Non-empty | — |
| `field.data_type` | `str` | Non-empty | From `information_schema.columns`. |
| `field.nullable` | `bool` | — | From source. |
| `field.sample_values` | `list[str]` | `0..5` | From live `run_query` sample (top-5). |
| `field.is_measure` | `bool` | — | Agent-inferred; user-editable. |
| `field.role` | `Literal["id", "dimension", "measure", "attribute"]` | — | Dimensional modeling role. |

**Maps to FR**: FR-007.

### `PrdSection` (Step 1)

| Field | Type | Validation | Notes |
|---|---|---|---|
| `heading` | `str` | Non-empty | e.g., "Problem Statement". |
| `body` | `str` | Markdown | Grounded in source schema per FR-005. |
| `cited_tables` | `list[str]` | Each matches a scanned source table | Required for every non-boilerplate section. |
| `completeness_contribution` | `float` | 0.0..1.0 | Fed into existing DSA `scoring.ts`. |

**Maps to FR**: FR-005.

### `DbtArtifactHandle` (Step 4)

| Field | Type | Validation | Notes |
|---|---|---|---|
| `handle` | `UUID` | — | Ephemeral download key. |
| `expires_at` | `datetime` | `issued_at + 60s` | Single-use, 60s TTL. |
| `file_count` | `int` | >= 1 | — |
| `size_bytes` | `int` | >= 1 | Zip size. |
| `download_url` | `str` | Relative path | `/workflow/artifact/{handle}` |

**Server-side state**: `app.state.artifact_store: dict[UUID, tuple[bytes, datetime]]` guarded by `asyncio.Lock`. Sweep task drops expired entries every 60s.

**Maps to FR**: FR-008, Clarify Q2.

---

## 5. Conversation & Gate State

### `GateDecision` (Python, TypeScript mirror)

| Field | Type | Validation | Notes |
|---|---|---|---|
| `step_id` | `StepId` | — | Which gate. |
| `decision` | `Literal["approved", "rejected", "revise"]` | — | — |
| `decided_at` | `datetime` | — | Server clock. |
| `revision_note` | `str \| None` | Required when decision == "revise" | — |

**Persistence**: written to AgentCore Memory under the session's memory key as event-sourced entries. Not a separate datastore.

**Maps to FR**: FR-009, FR-010.

### `WorkflowState` (derived projection, not stored directly)

Reconstructed at session-resume time by folding the Memory event stream:

| Field | Derivation |
|---|---|
| `current_step` | Latest `step_advanced` event, default REQUIREMENTS. |
| `completed_steps` | Set of `step_id` with an `approved` `GateDecision`. |
| `invalidated_steps` | Steps downstream of a re-run gate if user chose "invalidate." |
| `active_artifacts` | Latest `artifact_update` payload per `StepId` + `artifact_type`. |
| `chat_history` | Ordered list of `message` events. |

**Maps to FR**: FR-009, FR-010, FR-028, FR-029, FR-030.

---

## 6. Demo Mode

Entirely frontend; no backend model. TypeScript only:

```typescript
interface DemoModeState {
  enabled: boolean;
  reason: 'user_toggle' | 'auto_fallback' | null;
  activatedAt: string | null;  // ISO8601
}
```

Part of `AppContext` reducer state. Mutations: `DEMO_MODE_ENABLE`, `DEMO_MODE_DISABLE`, `DEMO_MODE_AUTO_ENABLE`.

**Maps to FR**: FR-015, FR-016, FR-017, FR-018.

---

## 7. State Transitions

### Session lifecycle (per tab)

```
 ┌────────┐      mount       ┌──────────┐     fetch /health    ┌─────────────┐
 │  null  │ ───────────────▶ │  minted  │ ───────────────────▶ │   active    │
 └────────┘                  └──────────┘                      └─────────────┘
                                                                      │
                                                                      │  tab close
                                                                      ▼
                                                                ┌───────────┐
                                                                │ discarded │
                                                                └───────────┘
```

- `null`: `sessionStorage["dsa_session_id"]` is empty (first visit).
- `minted`: UUID created, stored, but no backend contact yet.
- `active`: backend has acknowledged at least one request.
- `discarded`: tab close wipes sessionStorage. No resume path.

### Workflow state machine

```
 REQUIREMENTS ──approve──▶ CONCEPTUAL ──approve──▶ LOGICAL ──approve──▶ DETAILED ──approve──▶ COMPLETED
      │                        │                       │                    │
      ▼ revise                 ▼ revise                ▼ revise             ▼ revise
  (same step)              (same step)             (same step)          (same step)
      │
      ▼ user switches DB mid-session (FR-028)
  (all artifacts invalidated after explicit confirmation)
```

### Artifact lifecycle (Step 4 zip)

```
 generating ─ zip_built ─▶ handle_issued ──download──▶ consumed
                              │
                              ▼ 60s no download
                           expired (dropped by sweep task)
```

---

## 8. Validation Summary

| Rule | Enforced By |
|---|---|
| Session ID must be UUIDv4 | `SessionContext` validator |
| Credentials never persisted | Lint rule (no `SourceConnection` import outside allowed modules) + absence of storage code |
| Artifact handle is single-use and TTL-bound | `zip_stream.py` handle store + sweep task |
| Step can only consume prior-step artifacts | `StepRequest` validator |
| Allowed tools per step | Strands `agent` call wrapped with tool filter in step handler |
| SSE event shapes match schema | Pydantic models + contract tests round-trip encode/decode |
| Progress event at least every 30s | Passive emitter (10s cadence) + tool-level heartbeats |

All validations are testable; contract and integration tests land in `tests/contract/` and `tests/integration/` (see plan §Source Code).
