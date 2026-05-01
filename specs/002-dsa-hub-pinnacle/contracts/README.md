# API Contracts — DSA Hub Pinnacle Cross-Source

Each `.openapi.yaml` file in this directory is the authoritative contract for a slice of the new feature surface. Routes are mounted under the existing FastAPI app (`src/platform_agent/api/app.py`); these files define request/response shapes, status codes, and headers.

Common conventions:

- **Auth header**: `X-DSA-Session-ID: <uuid>` is the per-tab session UUID (existing). For one minor version, `X-DSA-Workspace-ID: <uuid>` is accepted as a synonym (FR-006).
- **Read-only enforcement**: Any field of type `sql` (in any contract) is rejected with `400 read_only_violation` if it contains write keywords (regex match against `INSERT|UPDATE|DELETE|DROP|TRUNCATE|ALTER|MERGE|GRANT|REVOKE|CREATE\s+(?!OR\s+REPLACE\s+VIEW)`).
- **Row caps**: Per-source pulls in cross-source TTYD are capped at 250 rows; joined results at 5,000 rows. Truncation is signaled in the response body, never silently.
- **SSE event schema**: Provisioning event streams use schema **v2**, additive over the existing v1 parser (`frontend/src/lib/agentcore-client/parsers/v1`). New parser at `parsers/v2`.

Files in this directory:

| File | Surface | New routes |
|---|---|---|
| `workspace.openapi.yaml` | Connection CRUD + workspace KPIs | `POST/DELETE/GET /workspace/connection(s)`, `GET /workspace/kpis` |
| `discover.openapi.yaml` | Multi-source discovery (extends existing) | `POST /workflow/discover` (workspace-scoped variant) |
| `pills.openapi.yaml` | Schema-grounded pill generation | `POST /workflow/pills`, `POST /workflow/pills/{pill_id}/draft-prd` |
| `redundancy.openapi.yaml` | Pre-acceptance gate | `POST /workflow/redundancy-check` |
| `provision.openapi.yaml` | 7-agent orchestrator + SSE stream v2 | `POST /workflow/provision`, `GET /workflow/provision/{run_id}/events`, `POST /workflow/provision/{run_id}/retry` |
| `semantic.openapi.yaml` | Per-connection graph reads | `GET /semantic/graph`, `GET /semantic/entities/{entity_id}` |
| `ttyd-cross-source.openapi.yaml` | Cross-source TTYD extensions to existing query route | `POST /workflow/query` (extended; backward-compatible) |

All endpoints inherit the existing `/health` check (`GET /health` → `{mode: "local"|"deployed", ...}`).
