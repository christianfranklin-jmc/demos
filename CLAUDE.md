# AWS Platform Agent

AI-powered data engineering agent that automates the journey from raw database schema to a working, queryable data product on AWS.

## Current State (as of 2026-04-02)

### Branches

**`main` branch** — Single-agent architecture, fully deployed end-to-end:
- RDS PostgreSQL + Redshift Serverless drivers (Snowflake driver on snow-iceberg-migration branch only)
- Streamlit "Talk To Your Data" app (phData dark theme, local agent)
- React frontend on Amplify (phData dark theme, Cognito auth, AgentCore streaming)
- CLI agent (`python -m platform_agent`)
- dbt project generation (Northwinds on PostgreSQL)
- Modular bootstrap/teardown scripts with `--services` flag (rds, redshift, snowflake, terraform, all)
- AgentCore fully deployed and working:
  - Runtime: `platform_agent_runtime-OfViSJB74e` (arm64 container, all 7 tools, auto-connects to DB)
  - Gateway: `platform-agent-gateway-wwjorrqn4v` (5 Lambda data tools via MCP)
  - Memory: `platform_agent_memory-3Z2bC62Ztv` (30-day retention)
  - Cognito: `us-east-1_iQ70gh7t7` (PKCE auth, admin: mwebb@phdata.io)
  - Amplify: `https://main.d2fj6tk58y0pxw.amplifyapp.com`

**`snow-iceberg-migration` branch** — 5-agent architecture for Snowflake → AWS migration:
- 5 specialized agents: Migration, Enrichment, Quality, Mapping, Query
- Migration Agent tested against Pinnacle Financial Snowflake (9 tables, dbt runs clean)
- Gateway Lambda extensions (snowflake_tools, iceberg_tools)
- dbt MCP Server integration config
- ADRs 012-014 (multi-agent orchestration, Iceberg migration, dbt MCP)
- NOT YET: Terraform deployed, AgentCore running, Step Functions orchestration

### What Works Right Now

```bash
# Local (Streamlit) — quickest demo
./scripts/bootstrap.sh --profile AdministratorAccess-637119802057 --services rds
source .env
uv run streamlit run streamlit_app/app.py --server.port 8501

# Full AWS (AgentCore + React + Cognito + Amplify)
./scripts/bootstrap.sh --profile AdministratorAccess-637119802057 --services rds,terraform
# Then set Cognito password and open Amplify URL (see PLAN.md)
```

### What's NOT Working / Known Issues

- Gateway target via Terraform: provider bug with `tool_schema` — registered via CLI workaround
- Runtime image updates via CLI clear JWT auth config — always use `terraform apply`
- Cognito auth flows managed by Terraform — manual CLI changes get reverted on next apply
- Docker images must be `linux/arm64` (AgentCore requirement)
- Amplify zip must contain files at root (not wrapped in dist/ folder)
- Redshift seeding: bootstrap.sh adapts types (bytea/text), untested on live cluster
- The 5-agent architecture is on `snow-iceberg-migration` branch only

## Tech Stack

- **Language**: Python 3.12+
- **Agent Framework**: Strands Agents SDK (`strands-agents`)
- **LLM**: Amazon Bedrock — Claude Sonnet 4 (default), Opus 4 (complex tasks)
- **Deployment**: Amazon Bedrock AgentCore Runtime (FAST template, Docker, arm64)
- **Infrastructure**: Terraform (FAST `infra-terraform/` three-module hierarchy)
- **Data Layer**: Multi-database driver abstraction (`DatabaseDriver` protocol) — PostgreSQL (psycopg2), Redshift (redshift_connector)
- **Transforms**: dbt-postgres, dbt-redshift (driver-selected)
- **Gateway**: AgentCore MCP Gateway — 5 data tools as Lambda targets
- **Observability**: OpenTelemetry auto-instrumentation → CloudWatch Traces
- **Evaluation**: AgentCore built-in evaluators (on-demand + online)
- **Auth**: Amazon Cognito (PKCE for frontend, OAuth2 M2M for Gateway)
- **Frontend**: Streamlit (local demo) + React + Vite + Tailwind (Amplify, Cognito auth)
- **SSE Client**: Multi-parser agentcore-client (strands, langgraph, claude-agent-sdk, agui, converse)
- **Package Manager**: uv (not pip)

## Directory Layout

```
src/platform_agent/               # Agent source code
  agent.py                        # Strands Agent factory — create_agent()
  models.py                       # BedrockModel config (Sonnet 4, Opus 4)
  __main__.py                     # Interactive CLI entry point
  serve.py                        # AgentCore Runtime entry point (AG-UI protocol)
  prompts/system.py               # System prompt (7 capabilities + guardrails)
  drivers/                        # Multi-database abstraction layer
    base.py                       # DatabaseDriver protocol definition
    __init__.py                   # Driver registry + create_driver()/get_driver()
    postgresql.py                 # PostgreSQL driver (psycopg2)
    redshift.py                   # Redshift driver (redshift_connector)
  tools/
    _toolkit_client.py            # Adapter: Toolkit CLI + driver layer
    toolkit_connect.py            # @tool connect_to_database (driver_type param)
    toolkit_scan.py               # @tool scan_metadata, profile_database
    toolkit_query.py              # @tool run_query (read-only SQL)
    toolkit_ddl.py                # @tool execute_ddl (DROP/TRUNCATE blocked)
    dbt_generate.py               # @tool generate_dbt_project (star schema → dbt)
    semantic_layer.py             # @tool generate_semantic_layer (MetricFlow YAML)
patterns/platform-agent/          # AgentCore container pattern
  agent.py                        # BedrockAgentCoreApp + all 7 tools + auto-connect
  Dockerfile                      # arm64, copies src/platform_agent/ for tools
  tools/                          # Direct tools (dbt_generate, semantic_layer)
  prompts/                        # System prompt
patterns/utils/                   # Shared utilities (from FAST template)
  auth.py                         # JWT extraction + OAuth2 token management
  ssm.py                          # SSM parameter retrieval
infra-terraform/                  # Terraform infrastructure (deployed)
  main.tf                         # Root: amplify-hosting → cognito → backend
  variables.tf                    # Stack config (name, pattern, network mode)
  modules/amplify-hosting/        # S3 + Amplify App (SPA rewrite rule)
  modules/cognito/                # User Pool + OAuth2 clients (PKCE + M2M)
  modules/backend/                # Runtime, Gateway, Memory, OAuth2 provider
frontend/                         # React + Vite + TypeScript + Tailwind
  src/App.tsx                     # Chat UI (dark theme, Cognito auth, AgentCore streaming)
  src/lib/agentcore-client/       # FAST SSE streaming client (5 parsers)
  src/lib/auth.ts                 # Cognito PKCE auth (login, callback, tokens)
  .env.production                 # Baked Amplify/Cognito/Runtime config
gateway/tools/data_tools/         # Lambda-backed Gateway tools (5 data tools)
eval/                             # Evaluation scripts + test cases
docker/docker-compose.yml         # Local dev compose (agent + frontend)
docs/adr/                         # Architecture Decision Records
dbt_output/northwinds_dw/         # Generated dbt project for PostgreSQL (14 models)
tests/                            # Unit and integration tests
test-scripts/                     # FAST infra validation (agent, gateway, memory)
tools/code_interpreter/           # AgentCore Code Interpreter (sandboxed Python)
streamlit_app/
  app.py                          # Streamlit TTYD app (phData dark theme)
  .streamlit/config.toml          # Dark theme config
scripts/
  bootstrap.sh                    # Provision databases + terraform + docker + amplify
  teardown.sh                     # Remove resources (--services rds,terraform,all)
  seed_northwinds.sql             # Northwinds DDL + 3362 INSERT statements
  deploy-frontend.py              # Amplify frontend deployment (from FAST)
  utils.py                        # Shared test/deploy utilities
PLAN.md                           # Build plan with from-scratch guides
.specify/memory/constitution.md   # Project constitution v2.1.0
.env.example                      # Template for env vars (copy to .env)
```

## Quick Start

```bash
# Local (Streamlit demo)
./scripts/bootstrap.sh --profile AdministratorAccess-637119802057 --services rds
source .env && uv run streamlit run streamlit_app/app.py --server.port 8501

# Full AWS (AgentCore + React + Cognito + Amplify)
./scripts/bootstrap.sh --profile AdministratorAccess-637119802057 --services rds,terraform

# Tear down
./scripts/teardown.sh --profile AdministratorAccess-637119802057 --services rds       # DB only
./scripts/teardown.sh --profile AdministratorAccess-637119802057 --services terraform # AWS only
./scripts/teardown.sh --profile AdministratorAccess-637119802057 --services all       # Everything
```

See PLAN.md for detailed from-scratch guides.

## Development Commands

```bash
uv pip install -e ".[dev]"              # Install core deps
uv pip install -e ".[redshift]"         # Add Redshift driver support
uv run pytest                           # Run tests
uv run ruff check src/ tests/ patterns/ # Lint
uv run ruff format src/ tests/ patterns/ # Format
```

## AWS Environment

- **Account**: 637119802057
- **Profile**: `AdministratorAccess-637119802057`
- **Region**: us-east-1
- **RDS**: PostgreSQL 16.6, db.t3.micro, Northwinds (14 tables, 830 orders)
- **Redshift**: Serverless, 8 base RPU (partially seeded)
- **Bedrock**: us.anthropic.claude-sonnet-4, us.anthropic.claude-opus-4
- **AgentCore Runtime**: `platform_agent_runtime-OfViSJB74e`
- **AgentCore Gateway**: `platform-agent-gateway-wwjorrqn4v` (5 tools)
- **AgentCore Memory**: `platform_agent_memory-3Z2bC62Ztv`
- **Cognito**: `us-east-1_iQ70gh7t7` (web client: `18nqacih7h0drtth8ghobmlsac`)
- **Amplify**: `https://main.d2fj6tk58y0pxw.amplifyapp.com`
- **ECR**: `637119802057.dkr.ecr.us-east-1.amazonaws.com/platform-agent-agent`

## Coding Conventions

- Type hints on all function signatures
- Docstrings on all `@tool` functions (they become LLM-visible descriptions)
- `ruff` for linting and formatting (line length: 99)
- One tool per file in `src/platform_agent/tools/`
- One driver per file in `src/platform_agent/drivers/`
- `DatabaseDriver` protocol for all database backends
- Tests mirror source structure: `tests/unit/`, `tests/integration/`
- Use `uv` (not pip) for all Python package management
- Dark mode default, phData brand palette for all UIs
- See `.specify/memory/constitution.md` for full principles (v2.1.0)

## Build Progress

### Main Branch — Complete through Phase 3
- **Phase 0-6**: Agent scaffold, tools, discovery, dbt, semantic layer, AgentCore serve.py
- **Phase 7**: FAST template — Terraform, drivers, Gateway, Memory, OTel, React, Cognito, Docker
- **Phase 8**: Constitution v2.1.0, PLAN.md, phData dark branding, FAST components pulled
- **Phase 9**: Terraform deployed (45 resources), Docker image pushed (arm64), Gateway target registered
- **Phase 10**: React frontend — Cognito PKCE auth, agentcore-client streaming, Converse parser fix, Amplify deployed
- **Phase 11**: Agent container updated with all 7 tools + auto-connect, IAM cross-region Bedrock fix
- **Phase 12**: Bootstrap/teardown --services terraform flag, from-scratch documentation

### Snow-Iceberg-Migration Branch — Phases 0-4
- 5 agent scaffolds, Snowflake driver, Gateway Lambdas, dbt MCP, ADRs 012-014
- Migration Agent tested against Pinnacle Financial (9 models, all pass)
- Enrichment, Quality, Mapping, Query agents scaffolded
- NOT YET: Terraform deployed, AgentCore running, Step Functions orchestration
