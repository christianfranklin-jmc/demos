# Contract: Session-ID Header

**Header name**: `X-DSA-Session-ID`
**Value**: UUIDv4 string (lowercased, hyphenated per RFC 4122)
**Lifetime**: per browser tab, stored in `sessionStorage["dsa_session_id"]`

---

## Frontend responsibilities

**File**: `frontend/src/lib/session.ts`

Exposes:

```ts
export function getOrMintSessionId(): string;
export function currentSessionId(): string | null;
export function clearSession(): void;  // used by "Start new session" if we ever add one
```

Invariants enforced by the module:
- First call to `getOrMintSessionId()` in a tab synchronously mints a new UUID via `crypto.randomUUID()` and stores it. Subsequent calls return the stored value unchanged.
- `getOrMintSessionId()` MUST be invoked once in `AppContext`'s initial effect so every outbound request can read it from a module-level cache.
- The module does NOT touch `localStorage`. Ever.

Every outbound request from `agentcore-client` adds the header:

```ts
headers: {
  'Content-Type': 'application/json',
  'Accept': 'text/event-stream',
  'X-DSA-Session-ID': getOrMintSessionId(),
  ...(jwt ? { Authorization: `Bearer ${jwt}` } : {}),
}
```

---

## Backend responsibilities

**File**: `src/platform_agent/api/deps.py`

FastAPI dependency:

```python
async def get_session_context(
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
    x_dsa_session_id: Annotated[str | None, Header(alias="X-DSA-Session-ID")] = None,
) -> SessionContext:
    if not x_dsa_session_id:
        raise HTTPException(400, "Missing X-DSA-Session-ID header")
    try:
        session_id = UUID(x_dsa_session_id)
    except ValueError:
        raise HTTPException(400, "X-DSA-Session-ID is not a valid UUID")
    ...
```

Validations applied:
1. Header MUST be present on every `/workflow/*` request (not required on `/health`).
2. MUST parse as a valid UUID (any version — we accept clients that mint v7 or v1 too).
3. In deployed mode, the JWT's `sub` is extracted and combined with `session_id` to form the Memory key (see `MemoryKey` in data-model.md).
4. In local mode (no `Authorization` header), the memory key uses `user_scope="local"`.

---

## Memory-key derivation

```python
def memory_key_for(session: SessionContext) -> str:
    user_scope = session.cognito_sub or "local"
    return f"dsa:{user_scope}:{session.session_id}"
```

Example: `dsa:a1b2c3…:550e8400-e29b-41d4-a716-446655440000`.

AgentCore Memory uses this string as the conversation key. 30-day retention (existing policy) applies.

---

## Session-ID conflict semantics

Two separate JWT identities presenting the same session UUID is astronomically unlikely, but the memory key's `user_scope` prefix makes a collision harmless — the conversations are stored under distinct keys. We therefore do NOT reject such requests in code; the `409 session_conflict` response documented in `http-endpoints.md` is reserved for a future stricter mode and is not currently emitted.

---

## Contract tests

Live in `tests/contract/test_session_header.py`:

- Missing header → 400 with body `{"error": {"code": "validation_error", "field": "X-DSA-Session-ID"}}`.
- Malformed UUID → 400.
- Valid UUID + JWT → `SessionContext.mode == "deployed"`, `cognito_sub` populated.
- Valid UUID, no JWT, local origin → `SessionContext.mode == "local"`, `cognito_sub is None`.
- Memory-key derivation matches the formula for both modes.
