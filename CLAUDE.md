# AWS Platform Agent

AI-powered data engineering agent that automates the journey from raw database schema to a working, queryable data product on AWS.

## Tech Stack

- **Language**: Python 3.12+
- **Agent Framework**: Strands Agents SDK (`strands-agents`)
- **LLM**: Amazon Bedrock — Claude Sonnet 4 (default), Opus 4 (complex tasks)
- **Deployment**: Amazon Bedrock AgentCore Runtime (FAST template, Docker)
- **Infrastructure**: Terraform (FAST `infra-terraform/` three-module hierarchy)
- **Data Layer**: Multi-database driver abstraction (`DatabaseDriver` protocol) — PostgreSQL (psycopg2), Redshift (redshift_connector), Snowflake/Databricks (future). phData Toolkit CLI as optional enhancement.
- **Transforms**: dbt-postgres, dbt-redshift (driver-selected)
- **Gateway**: AgentCore MCP Gateway — 5 data tools as Lambda targets
- **Observability**: OpenTelemetry auto-instrumentation → CloudWatch Traces
- **Evaluation**: AgentCore built-in evaluators (on-demand + online)
- **Auth**: Amazon Cognito (JWT for frontend, OAuth2 M2M for Gateway)
- **Frontend**: React + Vite + shadcn/ui (Amplify hosted) + Streamlit (preserved)
- **Package Manager**: uv (not pip)

## Directory Layout

```
src/platform_agent/               # Agent source code
  agent.py                        # Strands Agent factory — create_agent()
  models.py                       # BedrockModel config (Sonnet 4, Opus 4)
  __main__.py                     # Interactive CLI entry point
  serve.py                        # AgentCore Runtime entry point (AG-UI protocol, legacy)
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
patterns/platform-agent/          # FAST agent pattern (AgentCore Runtime)
  agent.py                        # BedrockAgentCoreApp + @app.entrypoint
  Dockerfile                      # Container image with OTel instrumentation
  tools/                          # Direct tools (dbt_generate, semantic_layer)
  prompts/                        # System prompt (copied from src/)
patterns/utils/                   # Shared utilities (from FAST template)
  auth.py                         # JWT extraction + OAuth2 token management
  ssm.py                          # SSM parameter retrieval
infra-terraform/                  # Terraform infrastructure (FAST template)
  main.tf                         # Root: amplify-hosting → cognito → backend
  variables.tf                    # Stack config (name, pattern, network mode)
  modules/amplify-hosting/        # S3 + Amplify App
  modules/cognito/                # User Pool + OAuth2 clients
  modules/backend/                # Runtime, Gateway, Memory, OAuth2 provider
gateway/tools/data_tools/         # Lambda-backed Gateway tools
  lambda_function.py              # 5 data tools (connect, scan, profile, query, DDL)
frontend/                         # React + Vite + TypeScript + shadcn/ui
eval/                             # Evaluation scripts + test cases
docker/docker-compose.yml         # Local dev compose (agent + frontend)
docs/adr/                         # Architecture Decision Records (11 ADRs)
dbt_output/northwinds_dw/         # Generated dbt project (14 models, compiles clean)
tests/                            # Unit and integration tests
streamlit_app/app.py              # Streamlit TTYD app (preserved as alternative)
scripts/
  bootstrap.sh                    # Provision RDS + seed data + config files
  teardown.sh                     # Remove AWS resources + terraform destroy
  seed_northwinds.sql             # Northwinds DDL + 3362 INSERT statements
.env.example                      # Template for env vars (copy to .env)
```

## Quick Start (from scratch)

The AWS instance self-deletes every few days. To recreate everything:

```bash
# Prerequisites: AWS CLI v2, psql, uv, Terraform >= 1.5, this repo
# 1. Bootstrap RDS infrastructure + seed data + config files
./scripts/bootstrap.sh --profile AdministratorAccess-637119802057

# 2. Source the generated .env
source .env

# 3. Deploy AgentCore infrastructure (Gateway, Runtime, Memory, Cognito, Amplify)
cd infra-terraform
cp terraform.tfvars.example terraform.tfvars  # Edit stack_name_base
terraform init && terraform apply
cd ..

# 4. Run the agent interactively (CLI)
uv run python -m platform_agent --profile $AWS_PROFILE

# 5. Or run the Streamlit app
uv run streamlit run streamlit_app/app.py --server.port 8501

# 6. Or run via Docker Compose (agent + React frontend)
cd docker && docker-compose up --build

# 7. Compile/run dbt models
uv run dbt deps --project-dir dbt_output/northwinds_dw --profiles-dir dbt_output/northwinds_dw
uv run dbt run --project-dir dbt_output/northwinds_dw --profiles-dir dbt_output/northwinds_dw
```

To tear down: `./scripts/teardown.sh --profile AdministratorAccess-637119802057`

## Development Commands

```bash
uv pip install -e ".[dev]"              # Install core deps
uv pip install -e ".[redshift]"         # Add Redshift driver support
uv pip install -e ".[otel]"             # Add OpenTelemetry support
uv run pytest                           # Run tests
uv run ruff check src/ tests/ patterns/ # Lint
uv run ruff format src/ tests/ patterns/ # Format

# Terraform
cd infra-terraform
terraform init                          # Initialize providers
terraform plan                          # Preview changes
terraform apply                         # Deploy

# Docker (local dev)
cd docker && docker-compose up --build  # Agent + frontend
```

## Multi-Database Support

The agent supports multiple database backends via the `DatabaseDriver` protocol (`src/platform_agent/drivers/base.py`). Each driver implements: connect, query, DDL, scan_metadata, profile_columns, and dbt config.

**Supported:**
| Database | Driver | Install | dbt Adapter |
|----------|--------|---------|-------------|
| PostgreSQL | psycopg2 | (included) | dbt-postgres |
| Redshift | redshift_connector | `uv pip install -e ".[redshift]"` | dbt-redshift |

**Planned:**
| Database | Driver | Install | dbt Adapter |
|----------|--------|---------|-------------|
| Snowflake | snowflake-connector-python | `uv pip install -e ".[snowflake]"` | dbt-snowflake |
| Databricks | databricks-sql-connector | `uv pip install -e ".[databricks]"` | dbt-databricks |

**Adding a new database:**
1. Create `src/platform_agent/drivers/<name>.py` implementing `DatabaseDriver`
2. Add connector to `pyproject.toml` optional deps
3. Register in `DRIVER_REGISTRY` in `drivers/__init__.py`
4. All tools, Gateway Lambda, and dbt generation work automatically

## AWS Environment

- **Account**: 637119802057
- **Profile**: `AdministratorAccess-637119802057`
- **Region**: us-east-1
- **RDS**: Provisioned by `scripts/bootstrap.sh` — PostgreSQL 16.6, db.t3.micro, Northwinds dataset
- **Bedrock models**: us.anthropic.claude-sonnet-4, us.anthropic.claude-opus-4

### Bootstrap creates:
- Security group (`platform-agent-rds-sg`, port 5432 open)
- DB subnet group (`platform-agent-db-subnets`)
- RDS instance (`platform-agent-northwinds`)
- Seeds Northwinds (14 tables, 830 orders)
- Generates `.env`, `toolkit.conf`, `dbt_output/northwinds_dw/profiles.yml`

### Terraform creates (infra-terraform/):
- Cognito User Pool + OAuth2 clients (web + machine)
- Amplify App (React frontend hosting)
- AgentCore Runtime (Docker container)
- AgentCore Gateway (MCP, Lambda target for 5 data tools)
- AgentCore Memory (30-day conversation retention)
- OAuth2 credential provider (M2M auth)
- SSM parameters + Secrets Manager for config

## Coding Conventions

- Type hints on all function signatures
- Docstrings on all `@tool` functions (they become LLM-visible descriptions)
- `ruff` for linting and formatting (line length: 99)
- One tool per file in `src/platform_agent/tools/`
- One driver per file in `src/platform_agent/drivers/`
- `DatabaseDriver` protocol for all database backends
- Tests mirror source structure: `tests/unit/`, `tests/integration/`

## Build Progress

Phases completed:
- **Phase 0**: Project scaffold + ADR log
- **Phase 1**: Core Strands agent with Bedrock round-trip
- **Phase 2**: Toolkit integration (5 tools, tested E2E against Northwinds)
- **Phase 3**: Interactive discovery — system prompt with Discovery Guide, Dimensional Modeling Guide, dbt Standards, Guardrails
- **Phase 4**: dbt code generation — `generate_dbt_project` tool produces full dbt project. Northwinds star schema: 8 staging, 6 marts, compiles clean
- **Phase 5**: Semantic layer tool + Streamlit TTYD app. Agent learns schema dynamically.
- **Phase 6**: AgentCore deployment — `serve.py` AG-UI protocol adapter

- **Phase 7**: FAST template integration — Terraform infrastructure (3-module hierarchy), multi-database driver abstraction (PostgreSQL + Redshift), AgentCore Gateway (5 Lambda tools), AgentCore Memory (30-day retention), Observability (OTel auto-instrumentation → CloudWatch), Evaluation (on-demand + 10% online sampling), React frontend (Vite + TypeScript + agentcore-client SSE), Cognito auth (JWT + OAuth2 M2M), Docker Compose local dev. ADRs 008-011. Branch: `redshift-agentcore-dbt`.

## dbt Project (Northwinds)

```bash
cd dbt_output/northwinds_dw
uv run dbt deps --profiles-dir .     # Install dbt_utils
uv run dbt compile --profiles-dir .  # Verify (14 models, 12 tests, 8 sources)
uv run dbt run --profiles-dir .      # Materialize to RDS
```

## Streamlit App (Talk To Your Data)

```bash
uv run streamlit run streamlit_app/app.py --server.port 8501
```

The app connects to any PostgreSQL database, runs `scan_metadata` to discover the schema, then accepts NL questions. The agent uses `run_query` to answer with actual data.

## AgentCore Deployment

### Legacy (serve.py — AG-UI adapter)
```bash
uv run --extra agentcore python -m platform_agent.serve
```

### FAST pattern (BedrockAgentCoreApp — in progress)
```bash
# Local via Docker Compose
cd docker && docker-compose up --build

# Deploy via Terraform
cd infra-terraform && terraform apply

# Environment variables (set by Terraform or .env)
export MEMORY_ID=...          # AgentCore Memory resource ID
export GATEWAY_URL=...        # AgentCore Gateway endpoint
export STACK_NAME=...         # Terraform stack name
export DB_HOST=... DB_PORT=5432 DB_NAME=northwinds DB_USER=postgres DB_PASSWORD=...
export DB_DRIVER_TYPE=postgresql  # or "redshift"
```

The FAST pattern uses `BedrockAgentCoreApp` with `@app.entrypoint`, replacing the manual AG-UI event mapping in `serve.py`. Gateway tools are discovered via MCP. Memory persists conversations across sessions.
