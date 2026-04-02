# AWS Platform Agent — Build Plan

AI-powered data engineering agent that automates the journey from raw
database schema to a working, queryable data product on AWS. Built for
phData client demos and internal enablement.

## Quick Start: Local (Streamlit)

Fastest path — runs the agent locally against a PostgreSQL database.

**Prerequisites:** AWS CLI v2, `psql`, `uv`

```bash
# 1. Bootstrap RDS only
./scripts/bootstrap.sh --profile AdministratorAccess-637119802057 --services rds

# 2. Run
source .env
uv run streamlit run streamlit_app/app.py --server.port 8501
```

## Quick Start: AWS (AgentCore + React)

Full cloud deployment — one command does everything.

**Prerequisites:** AWS CLI v2, `psql`, `uv`, Terraform >= 1.5, Node.js
18+, Docker Desktop running

```bash
# 1. Bootstrap RDS + Terraform + Docker + Amplify
./scripts/bootstrap.sh --profile AdministratorAccess-637119802057 --services rds,terraform

# 2. Set Cognito password (edit email + password)
source .env
aws cognito-idp admin-set-user-password \
  --user-pool-id "$(terraform -chdir=infra-terraform output -raw cognito_user_pool_id)" \
  --username YOUR_EMAIL --password 'YOUR_PASSWORD' \
  --permanent --region us-east-1

# 3. Open the app
terraform -chdir=infra-terraform output amplify_app_url
```

Edit `admin_user_email` in `infra-terraform/terraform.tfvars` before
running if you want a specific Cognito admin user created.

## Tear Down

```bash
# Local only (databases)
./scripts/teardown.sh --profile AdministratorAccess-637119802057 --services rds

# AWS only (AgentCore, Cognito, Amplify — keeps databases)
./scripts/teardown.sh --profile AdministratorAccess-637119802057 --services terraform

# Everything
./scripts/teardown.sh --profile AdministratorAccess-637119802057 --services all
```

## What Exists (main branch)

| Component | Status | Entry Point |
|-----------|--------|-------------|
| Strands Agent (single) | Working | `uv run python -m platform_agent` |
| Streamlit TTYD app | Working (dark, branded) | `uv run streamlit run streamlit_app/app.py` |
| React frontend | Deployed on Amplify | `https://main.<app-id>.amplifyapp.com` |
| PostgreSQL driver | Working | `src/platform_agent/drivers/postgresql.py` |
| Redshift driver | Working | `src/platform_agent/drivers/redshift.py` |
| AgentCore Runtime | Deployed | Container with all 7 tools |
| AgentCore Gateway | Deployed | 5 Lambda-backed data tools via MCP |
| AgentCore Memory | Deployed | 30-day conversation retention |
| Cognito auth | Deployed | PKCE flow, JWT for Runtime |
| dbt generation | Working | `generate_dbt_project` tool |
| Semantic layer | Working | `generate_semantic_layer` tool |
| Bootstrap/teardown | Working | `scripts/bootstrap.sh`, `scripts/teardown.sh` |
| AgentCore SSE client | Working | `frontend/src/lib/agentcore-client/` |
| Test scripts | Ready | `test-scripts/` (agent, gateway, memory) |
| Code Interpreter | Ready | `tools/code_interpreter/` |
| Constitution | v2.1.0 | `.specify/memory/constitution.md` |

## Known Issues

- **Gateway target via Terraform**: `aws_bedrockagentcore_gateway_target`
  has a provider bug with `tool_schema`. Register via CLI instead (see
  deployment steps above).
- **Runtime image updates**: `update-agent-runtime` via CLI clears the
  JWT authorizer config. Always use `terraform apply` to update the
  Runtime so auth config is preserved.
- **Cognito auth flows**: Terraform manages `explicit_auth_flows` on the
  Cognito client. Manual changes via CLI get reverted on next apply.
  Edit `infra-terraform/modules/cognito/main.tf` instead.
- **Docker architecture**: AgentCore Runtime requires `linux/arm64`
  images. Always build with `--platform linux/arm64`.
- **Amplify zip packaging**: Zip must contain files at root (not wrapped
  in a `dist/` directory). Always `cd dist && zip -r ... .`

## Architecture Notes

- Agent container includes full `src/platform_agent/` package (tools +
  drivers). The pattern's `agent.py` auto-connects to the database using
  `DB_*` environment variables set on the Runtime.
- Strands SSE stream emits Converse-format events (`contentBlockDelta`).
  The frontend `strands` parser handles both Converse and high-level
  Strands event formats.
- Cognito access tokens (not ID tokens) are used for Runtime auth.
  Runtime JWT authorizer validates `client_id` claim only — no
  `allowedAudience` (Cognito access tokens lack `aud`).

## Non-Negotiable Constraints

- Dark mode is the default for all UIs
- Python for everything except browser UI (React + TypeScript)
- `uv` for all Python packaging — no pip, poetry, conda
- `DatabaseDriver` protocol for all database access
- Read-only by default; writes require human approval
- phData brand palette for all visual output
- Backend mode (Local Agent vs AgentCore) must be visible to user
- Credentials never in source, logs, or agent responses
- Full environment reproducible from bootstrap.sh
- See `.specify/memory/constitution.md` for complete principles (v2.1.0)
