# AWS Platform Agent

AI-powered data engineering agent that automates the journey from raw database schema to a working, queryable data product on AWS.

## Current State (as of 2026-04-01)

### Branches

**`main` branch** — Single-agent architecture, working end-to-end:
- RDS PostgreSQL + Redshift Serverless + Snowflake connectivity (all three drivers)
- Streamlit "Talk To Your Data" app (primary demo interface)
- CLI agent (`python -m platform_agent`)
- dbt project generation (Northwinds on PostgreSQL, Pinnacle Financial on Snowflake)
- Modular bootstrap/teardown scripts with `--services` flag
- Terraform modules for AgentCore (validated, not yet deployed)
- AgentCore available in AWS account (CLI + SDK + Terraform provider confirmed)

**`snow-iceberg-migration` branch** — 5-agent architecture for Snowflake → AWS migration:
- 5 specialized agents: Migration, Enrichment, Quality, Mapping, Query
- Migration Agent tested against Pinnacle Financial Snowflake (9 tables, dbt runs clean)
- Gateway Lambda extensions (snowflake_tools, iceberg_tools)
- dbt MCP Server integration config
- ADRs 012-014 (multi-agent orchestration, Iceberg migration, dbt MCP)
- NOT YET: Terraform deployed, AgentCore running, Step Functions orchestration

### What Works Right Now (main branch)

```bash
# 1. Bootstrap RDS only (quickest demo)
./scripts/bootstrap.sh --profile AdministratorAccess-637119802057 --services rds

# 2. Source env and run Streamlit
source .env
uv run streamlit run streamlit_app/app.py --server.port 8501
```

Connect to PostgreSQL (Northwinds) or Snowflake (Pinnacle Financial) in the sidebar, then ask questions.

### What's NOT Working / Not Deployed

- AgentCore Runtime — Terraform validates but `terraform apply` not yet run
- AgentCore Gateway — same (Lambda + Gateway resources ready, not deployed)
- React frontend — scaffolded but needs running agent backend on port 8080
- Redshift seeding — tables exist (14) but most are empty (bytea/text type issues in seed SQL)
- The 5-agent architecture is on `snow-iceberg-migration` branch only

## Tech Stack

- **Language**: Python 3.12+
- **Agent Framework**: Strands Agents SDK (`strands-agents`)
- **LLM**: Amazon Bedrock — Claude Sonnet 4 (default), Opus 4 (complex tasks)
- **Deployment**: Amazon Bedrock AgentCore Runtime (FAST template, Docker)
- **Infrastructure**: Terraform (FAST `infra-terraform/` three-module hierarchy)
- **Data Layer**: Multi-database driver abstraction (`DatabaseDriver` protocol) — PostgreSQL (psycopg2), Redshift (redshift_connector), Snowflake (snowflake-connector-python). phData Toolkit CLI as optional enhancement.
- **Transforms**: dbt-postgres, dbt-redshift, dbt-snowflake (driver-selected)
- **Gateway**: AgentCore MCP Gateway — 5+ data tools as Lambda targets
- **Observability**: OpenTelemetry auto-instrumentation → CloudWatch Traces
- **Evaluation**: AgentCore built-in evaluators (on-demand + online)
- **Auth**: Amazon Cognito (JWT for frontend, OAuth2 M2M for Gateway)
- **Frontend**: Streamlit (primary, working) + React + Vite + shadcn/ui (scaffolded)
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
    snowflake.py                  # Snowflake driver (snowflake-connector-python)
  tools/
    _toolkit_client.py            # Adapter: Toolkit CLI + driver layer
    toolkit_connect.py            # @tool connect_to_database (driver_type param)
    toolkit_scan.py               # @tool scan_metadata, profile_database
    toolkit_query.py              # @tool run_query (read-only SQL)
    toolkit_ddl.py                # @tool execute_ddl (DROP/TRUNCATE blocked)
    dbt_generate.py               # @tool generate_dbt_project (star schema → dbt)
    semantic_layer.py             # @tool generate_semantic_layer (MetricFlow YAML)
patterns/platform-agent/          # FAST agent pattern (single generic agent)
  agent.py                        # BedrockAgentCoreApp + @app.entrypoint
  Dockerfile                      # Container image with OTel instrumentation
  tools/                          # Direct tools (dbt_generate, semantic_layer)
  prompts/                        # System prompt
patterns/migration-agent/         # Snowflake → Iceberg migration agent
patterns/enrichment-agent/        # RAG descriptions + DataZone + semantic YAML
patterns/quality-agent/           # DQDL rules + quarantine + dbt test
patterns/mapping-agent/           # Neptune graph + entity extraction + dbt lineage
patterns/query-agent/             # NL-to-SQL + semantic cache + self-correction
patterns/utils/                   # Shared utilities (from FAST template)
  auth.py                         # JWT extraction + OAuth2 token management
  ssm.py                          # SSM parameter retrieval
infra-terraform/                  # Terraform infrastructure (FAST template)
  main.tf                         # Root: amplify-hosting → cognito → backend
  variables.tf                    # Stack config (name, pattern, network mode)
  modules/amplify-hosting/        # S3 + Amplify App
  modules/cognito/                # User Pool + OAuth2 clients
  modules/backend/                # Runtime, Gateway, Memory, OAuth2 provider
  modules/data/                   # S3, Glue, Neptune, ElastiCache (snow-iceberg)
  modules/secrets/                # Secrets Manager (snow-iceberg)
  modules/events/                 # EventBridge + Step Functions (snow-iceberg)
gateway/tools/data_tools/         # Lambda-backed Gateway tools (5 data tools)
gateway/tools/snowflake_tools/    # Snowflake-specific Lambda (extract metadata, validate)
gateway/tools/iceberg_tools/      # Iceberg operations Lambda (convert, export, register)
gateway/mcp/                      # dbt MCP server config
frontend/                         # React + Vite + TypeScript + shadcn/ui
eval/                             # Evaluation scripts + test cases
docker/docker-compose.yml         # Local dev compose (agent + frontend)
docs/adr/                         # Architecture Decision Records (14 ADRs)
dbt_output/northwinds_dw/         # Generated dbt project for PostgreSQL (14 models)
dbt_output/pinnacle_dw/           # Generated dbt project for Snowflake (9 models)
tests/                            # Unit and integration tests
streamlit_app/app.py              # Streamlit TTYD app (primary demo interface)
scripts/
  bootstrap.sh                    # Provision RDS/Redshift/Snowflake + seed + config
  teardown.sh                     # Remove resources (supports --services flag)
  seed_northwinds.sql             # Northwinds DDL + 3362 INSERT statements
  setup-dbt-mcp.sh                # Install/verify dbt MCP server
.env.example                      # Template for env vars (copy to .env)
```

## Quick Start (from scratch)

The AWS instance self-deletes every few days. To recreate:

```bash
# Prerequisites: AWS CLI v2, psql, uv, Terraform >= 1.5, this repo

# 1. Bootstrap (modular — choose what you need)
./scripts/bootstrap.sh --profile AdministratorAccess-637119802057 --services rds
./scripts/bootstrap.sh --profile AdministratorAccess-637119802057 --services rds,redshift
./scripts/bootstrap.sh --profile AdministratorAccess-637119802057 --services all

# 2. Source the generated .env
source .env

# 3. Run the Streamlit app (quickest demo)
uv run streamlit run streamlit_app/app.py --server.port 8501

# 4. Or run the CLI agent
uv run python -m platform_agent --profile $AWS_PROFILE

# 5. Deploy AgentCore (optional — not required for Streamlit demo)
cd infra-terraform
cp terraform.tfvars.example terraform.tfvars  # Edit stack_name_base
terraform init && terraform apply
cd ..

# 6. Compile/run dbt models
uv run dbt deps --project-dir dbt_output/northwinds_dw --profiles-dir dbt_output/northwinds_dw
uv run dbt run --project-dir dbt_output/northwinds_dw --profiles-dir dbt_output/northwinds_dw
```

To tear down: `./scripts/teardown.sh --profile AdministratorAccess-637119802057 --services all`

## Bootstrap --services Flag

```bash
# RDS only (default, backward compatible)
./scripts/bootstrap.sh --profile P --services rds

# Redshift only
./scripts/bootstrap.sh --profile P --services redshift

# Both RDS + Redshift
./scripts/bootstrap.sh --profile P --services rds,redshift

# Snowflake config (writes SF_* vars to .env, no AWS provisioning)
./scripts/bootstrap.sh --profile P --services snowflake \
    --sf-account lga76011 --sf-user MWEBB@PHDATA.IO \
    --sf-database PINNACLE_FINANCIAL_DEMO_ASINGH --sf-role ALL_ML_ARCHITECTS

# Everything
./scripts/bootstrap.sh --profile P --services all
```

The bootstrap script:
- Resets RDS password on existing instances (fixes auth mismatch after re-bootstrap)
- Retries Redshift connectivity up to 2 min after workgroup creation
- Preserves existing .env vars when bootstrapping a subset of services
- Teardown supports the same --services flag for selective cleanup

## Development Commands

```bash
uv pip install -e ".[dev]"              # Install core deps
uv pip install -e ".[redshift]"         # Add Redshift driver support
uv pip install -e ".[snowflake]"        # Add Snowflake driver support
uv pip install -e ".[otel]"             # Add OpenTelemetry support
uv run pytest                           # Run tests
uv run ruff check src/ tests/ patterns/ # Lint
uv run ruff format src/ tests/ patterns/ # Format

# Terraform
cd infra-terraform
terraform init                          # Initialize providers
terraform validate                      # Validate config (passes)
terraform plan                          # Preview changes
terraform apply                         # Deploy AgentCore + Cognito + Amplify

# Docker (local dev)
cd docker && docker-compose up --build  # Agent + frontend
```

## Multi-Database Support

The agent supports multiple database backends via the `DatabaseDriver` protocol (`src/platform_agent/drivers/base.py`). Each driver implements: connect, query, DDL, scan_metadata, profile_columns, and dbt config.

| Database | Driver | Install | dbt Adapter | Status |
|----------|--------|---------|-------------|--------|
| PostgreSQL | psycopg2 | (included) | dbt-postgres | Working |
| Redshift | redshift_connector | `uv pip install -e ".[redshift]"` | dbt-redshift | Working (connectivity OK, seed partial) |
| Snowflake | snowflake-connector-python | `uv pip install -e ".[snowflake]"` | dbt-snowflake | Working (tested against Pinnacle Financial) |
| Databricks | databricks-sql-connector | `uv pip install -e ".[databricks]"` | dbt-databricks | Planned |

**Adding a new database:**
1. Create `src/platform_agent/drivers/<name>.py` implementing `DatabaseDriver`
2. Add connector to `pyproject.toml` optional deps
3. Register in `DRIVER_REGISTRY` in `drivers/__init__.py`
4. All tools, Gateway Lambda, and dbt generation work automatically

## AWS Environment

- **Account**: 637119802057
- **Profile**: `AdministratorAccess-637119802057`
- **Region**: us-east-1
- **RDS**: PostgreSQL 16.6, db.t3.micro, Northwinds (14 tables, 830 orders)
- **Redshift**: Serverless, 8 base RPU, Northwinds (14 tables, partially seeded)
- **Snowflake**: PINNACLE_FINANCIAL_DEMO_ASINGH.ANALYTICS (9 tables, SSO auth via externalbrowser)
- **Bedrock models**: us.anthropic.claude-sonnet-4, us.anthropic.claude-opus-4
- **AgentCore**: Available (CLI + SDK v1.4.7 + Terraform provider v6.39)

## Snowflake Connection (Pinnacle Financial)

```
Account:       lga76011 (PHDATAPARTNER-AWS)
User:          MWEBB@PHDATA.IO
Authenticator: externalbrowser (SSO — opens browser)
Role:          ALL_ML_ARCHITECTS
Warehouse:     COMPUTE_WH
Database:      PINNACLE_FINANCIAL_DEMO_ASINGH
Schema:        ANALYTICS
Tables:        9 (5 dims + 4 facts, total ~960 rows)
```

The Snowflake driver supports SSO via `externalbrowser` authenticator. When connecting, a browser window opens for authentication.

## Coding Conventions

- Type hints on all function signatures
- Docstrings on all `@tool` functions (they become LLM-visible descriptions)
- `ruff` for linting and formatting (line length: 99)
- One tool per file in `src/platform_agent/tools/`
- One driver per file in `src/platform_agent/drivers/`
- `DatabaseDriver` protocol for all database backends
- Tests mirror source structure: `tests/unit/`, `tests/integration/`
- Use `uv` (not pip) for all Python package management

## Build Progress

### Main Branch (Phases 0-7 + fixes)
- **Phase 0**: Project scaffold + ADR log
- **Phase 1**: Core Strands agent with Bedrock round-trip
- **Phase 2**: Toolkit integration (5 tools, tested E2E against Northwinds)
- **Phase 3**: Interactive discovery — system prompt with Discovery Guide, Dimensional Modeling Guide, dbt Standards, Guardrails
- **Phase 4**: dbt code generation — `generate_dbt_project` tool produces full dbt project
- **Phase 5**: Semantic layer tool + Streamlit TTYD app
- **Phase 6**: AgentCore deployment — `serve.py` AG-UI protocol adapter
- **Phase 7**: FAST template integration — Terraform, multi-database drivers, Gateway, Memory, OTel, Evaluation, React frontend, Cognito, Docker Compose. ADRs 008-011.
- **Fix**: Modular bootstrap (`--services` flag), RDS password reset, Redshift retry
- **Fix**: Terraform AgentCore resource schemas corrected for AWS provider v6

### Snow-Iceberg-Migration Branch (Phases 0-4)
- **Phase 0**: 5 agent scaffolds, Snowflake driver, Gateway Lambdas, dbt MCP, ADRs 012-014
- **Phase 1**: Migration Agent tools (extract_schema, convert_to_iceberg, validate_migration, generate_dbt_scaffold). Tested against Pinnacle Financial: 9 models, 18 tests, all pass.
- **Phase 2**: Enrichment Agent (RAG descriptions, DataZone, Glue metadata) + Quality Agent (DQDL, quarantine, dbt test, remediation)
- **Phase 3**: Mapping Agent (Neptune graph, entity extraction, dbt lineage) + Query Agent (NL-to-SQL, semantic cache, self-correction)
- **Phase 4**: Integration — frontend agent selector, per-agent evaluation, Step Functions orchestration config

### Next Steps
1. Deploy AgentCore via `terraform apply` (main branch — Terraform validates clean)
2. Build + push Docker image to ECR
3. Test agent via AgentCore Runtime endpoint
4. Merge snow-iceberg-migration into main when 5-agent pipeline is ready

## dbt Projects

### Northwinds (PostgreSQL)
```bash
uv run dbt deps --project-dir dbt_output/northwinds_dw --profiles-dir dbt_output/northwinds_dw
uv run dbt run --project-dir dbt_output/northwinds_dw --profiles-dir dbt_output/northwinds_dw
# 14 models, 12 tests, 8 sources — compiles and runs clean
```

### Pinnacle Financial (Snowflake)
```bash
uv run dbt run --project-dir dbt_output/pinnacle_dw --profiles-dir dbt_output/pinnacle_dw
uv run dbt test --project-dir dbt_output/pinnacle_dw --profiles-dir dbt_output/pinnacle_dw
# 9 models, 18 tests, 9 sources — all pass (requires Snowflake SSO)
```

## Streamlit App (Talk To Your Data)

```bash
uv run streamlit run streamlit_app/app.py --server.port 8501
```

The app connects to any PostgreSQL, Redshift, or Snowflake database (selectable via Database Type dropdown), runs `scan_metadata` to discover the schema, then accepts NL questions. The agent uses `run_query` to answer with actual data.

## AgentCore Deployment

### Status
- Terraform modules validated (AWS provider v6.39)
- `terraform apply` NOT YET RUN — AgentCore resources not deployed
- Python SDK: bedrock-agentcore v1.4.7 installed
- agentcore CLI: NOT installed (install with `uv pip install bedrock-agentcore-cli`)

### To Deploy
```bash
cd infra-terraform
cp terraform.tfvars.example terraform.tfvars  # Set stack_name_base
terraform init && terraform apply

# Then build and push Docker image
ECR_REPO=$(terraform output -raw ecr_repository_url)
docker build -f patterns/platform-agent/Dockerfile -t platform-agent .
docker tag platform-agent:latest $ECR_REPO:latest
aws ecr get-login-password | docker login --username AWS --password-stdin $ECR_REPO
docker push $ECR_REPO:latest
```

### FAST pattern (BedrockAgentCoreApp)
```bash
# Local via Docker Compose
cd docker && docker-compose up --build

# Environment variables (set by Terraform or .env)
export MEMORY_ID=...          # AgentCore Memory resource ID
export GATEWAY_URL=...        # AgentCore Gateway endpoint
export STACK_NAME=...         # Terraform stack name
```
