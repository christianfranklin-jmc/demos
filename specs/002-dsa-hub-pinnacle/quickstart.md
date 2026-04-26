# Quickstart — DSA Hub Pinnacle Cross-Source

Bring a fresh checkout of `002-dsa-hub-pinnacle` to a working multi-source demo.

## Prerequisites

- macOS / Linux dev box with Python 3.12+, Node 20+, AWS CLI v2, `psql`, `terraform >= 1.5`, Docker.
- AWS profile `AdministratorAccess-637119802057` configured (account 637119802057).
- Snowflake SSO access to the Pinnacle Financial demo account `lga76011`, role + warehouse + DB per CLAUDE.md.

## 1. Install dependencies

```bash
uv pip install -e ".[dev,redshift,snowflake,otel]"
uv add duckdb pyiceberg
cd frontend && pnpm install && cd ..
```

## 2. Bootstrap the Pinnacle Postgres seed (replaces Northwinds)

```bash
./scripts/bootstrap.sh --profile AdministratorAccess-637119802057
```

This now seeds **`scripts/seed_pinnacle.sql`** — the 8 business processes at the row volumes named in FR-042 (336 AP invoices / $5.6M, 1,680 fee invoices / $10.7M, $295M annual budget across 18,432 budget lines, 420 trades / $19.4M, 6,300 daily AUM snapshots, 15 employees, etc.). Idempotent; re-runs are safe.

The Snowflake side keeps the existing analytical mirror — no migration needed for v1. Apply `scripts/seed_pinnacle_snowflake.sql` against the demo account if shared business keys (`client_id`, `account_id`, `strategy_id`) need refreshing:

```bash
SF_USER=<you> SF_AUTHENTICATOR=externalbrowser \
  uv run python -m platform_agent.scripts.apply_snowflake_seed
```

## 3. Source the env

```bash
source .env
```

Bootstrap writes both `DB_*` (Pinnacle Postgres) and `SF_*` (Snowflake) variables. New env vars introduced by this feature:

| Var | Default | Purpose |
|---|---|---|
| `STORAGE_BACKEND` | `local` | `local` (SQLite under `~/.dsa-hub/connections/<id>/`) or `dynamodb` (deployed). |
| `DSA_HUB_VALIDATION_THRESHOLD` | `0.80` | Pass-rate gate that promotes a provisioning run's product from `provisional` to `final` (Q5). |
| `DSA_HUB_DUCKDB_JOIN_CAP` | `5000` | Joined-result row cap (FR-018). |
| `DSA_HUB_SOURCE_PULL_CAP` | `250` | Per-source pull row cap (FR-018). |
| `ICEBERG_DEFAULT_GLUE_DB` | _(unset)_ | Optional pre-config of a Glue DB the demo can attach as the Iceberg connection. |

## 4. Add the third connection: Iceberg / Glue

The platform will not let a PRD acceptance proceed without a live Iceberg connection (FR-031, Q3). Either:

- **Local mode**: provision a local Glue catalog DB via Terraform (`infra-terraform/modules/data` adds `aws_glue_catalog_database.dsa_hub_pinnacle_360`), apply, then add the connection in the UI as `driver_type=iceberg`, `endpoint=glue://us-east-1/<glue_db>`, `scope=<glue_db>`.
- **Deployed mode**: the Terraform module creates the Glue DB; the UI auto-suggests it as a candidate connection in the Add Connection modal.

The UI's Add Connection modal renders driver-specific forms; the Iceberg form takes Glue DB name + S3 warehouse URI + region.

## 5. Run

Three frontends, same backend:

```bash
# A. CLI (text-mode equivalent — three-frontend rule)
uv run python -m platform_agent --profile $AWS_PROFILE

# B. Streamlit (single-source preserved)
uv run streamlit run streamlit_app/app.py --server.port 8501

# C. React (primary)
cd frontend && pnpm dev
# in another shell: uv run uvicorn platform_agent.api.app:app --reload --port 8000
```

Or via Docker Compose (agent + React + DuckDB scratchpad in one shot):

```bash
cd docker && docker-compose up --build
```

## 6. Drive the showcase narrative (SC-001)

In the React app:

1. **Connections page** (`/connections`): add Pinnacle Postgres + Pinnacle Snowflake. The Iceberg/Glue connection is pre-staged in demo prep so the live "add" is just the two source sources.
2. **Step 1** (`/workflow/discovery`): wait ≤60 s for the 8 business-process cards + cross-source coverage matrix + 6 pills.
3. Click **Client 360** pill. The PRD draft opens in Step 2.
4. Walk Step 2 → Step 3 → Step 4 (existing flow continues to work). At Step 4, **Accept & Provision** triggers the redundancy gate.
5. Resolve any partial-overlap decisions; net-new for a fresh install.
6. The **Build page** (`/build/<run_id>`) opens automatically. Watch the 7-agent DAG run; KPI tiles tick.
7. The **Validation Card** auto-runs the PRD's three core questions. ≥ 80 % green → product registered as `final`, exposed to TTYD.
8. Switch lens to **All Pinnacle sources** in the ContextBar. Open TTYD and ask:
   > "Show me Q1 advisor productivity with AUM growth and meeting count, ranked."
   The response renders source chips for Postgres + Snowflake + DuckDB join + the new Iceberg product.

Total wall-clock target: ≤ 8 minutes (SC-001).

## 7. Demo mode (offline)

If you need to demo with no live AWS / DBs:

```bash
DSA_HUB_DEMO_MODE=1 cd frontend && pnpm dev
```

The `useAgent.demo.ts` engine ships a canned Pinnacle multi-source scenario — connections, processes, pills, provisioning DAG, validation, and TTYD all replay deterministically (FR-041, R9).

## 8. Tests

```bash
# Backend
uv run pytest                                     # All 51 existing + new contract tests
uv run pytest tests/contract/                     # New endpoint contracts only
uv run pytest tests/integration/test_provision.py # End-to-end provisioning DAG with stub agents
uv run mypy src/platform_agent/                   # Strict type-check NEW modules
uv run ruff check src/ tests/ patterns/

# Frontend
cd frontend
pnpm test                                         # Vitest cascade-invalidation suite + new state machine tests
pnpm test:e2e                                     # Optional Playwright run against `pnpm dev` + backend

# Eval
uv run python -m platform_agent.eval pill-agent
uv run python -m platform_agent.eval redundancy-agent
uv run python -m platform_agent.eval semantic-agent
uv run python -m platform_agent.eval delivery-agent
```

## 9. Tear down

```bash
./scripts/teardown.sh --profile AdministratorAccess-637119802057
# Also wipes ~/.dsa-hub/connections/* if --include-local is passed.
```

## 10. Troubleshooting

- **"No Iceberg target connection in workspace"** on PRD accept → add an `iceberg`-driver connection per step 4.
- **Discovery shows fewer than 8 processes** for Pinnacle Postgres → re-run `./scripts/bootstrap.sh` to confirm the seed; the discoverer asserts 8 by name in tests.
- **Validation pass rate stuck at 0.0** → check `delivery-agent` logs; the LLM-as-judge requires the SF + PG connections to remain `live` during validation. Reconnect in the Connections page if either is in `error`.
- **Cross-source TTYD returns "cross_source_unavailable"** → workspace has <2 live connections; verify both source cards show status=live.
- **Provisional product won't promote to final** → rerun the failed validation step; promotion is atomic on the rerun that lifts pass rate ≥ threshold.
