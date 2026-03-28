# AWS Platform Agent

AI-powered data engineering agent that automates the journey from raw database schema to a working, queryable data product on AWS. Connect to any PostgreSQL or Redshift database, discover its schema, design a dimensional model, generate a full dbt project, add a MetricFlow semantic layer, and query it all through natural language.

## Tech Stack

- **Language**: Python 3.12+
- **Agent Framework**: [Strands Agents SDK](https://github.com/strands-agents/strands-agents)
- **LLM**: Amazon Bedrock — Claude Sonnet 4 (default), Claude Opus 4 (complex tasks)
- **Deployment**: Amazon Bedrock AgentCore Runtime (FAST template, Docker)
- **Infrastructure**: Terraform (three-module hierarchy: amplify-hosting, cognito, backend)
- **Data Layer**: Multi-database driver abstraction (`DatabaseDriver` protocol) — PostgreSQL, Redshift
- **Transforms**: dbt-postgres, dbt-redshift (driver-selected)
- **Gateway**: AgentCore MCP Gateway — 5 data tools as Lambda targets
- **Observability**: OpenTelemetry auto-instrumentation → CloudWatch Traces
- **Evaluation**: AgentCore built-in evaluators (on-demand + online)
- **Auth**: Amazon Cognito (JWT for frontend, OAuth2 M2M for Gateway)
- **Frontend**: React + Vite + shadcn/ui (Amplify hosted) + Streamlit (preserved)
- **Package Manager**: uv (not pip)

## Quick Start

```bash
# 1. Bootstrap AWS infrastructure + seed Northwinds data
./scripts/bootstrap.sh --profile <YOUR_AWS_PROFILE>

# 2. Source the generated .env
source .env

# 3. Run the agent interactively
uv run python -m platform_agent --profile $AWS_PROFILE

# 4. Or run the Streamlit app
uv run streamlit run streamlit_app/app.py --server.port 8501

# 5. Deploy AgentCore infrastructure (Gateway, Runtime, Memory, Cognito, Amplify)
cd infra-terraform
cp terraform.tfvars.example terraform.tfvars  # Edit stack_name_base
terraform init && terraform apply
```

To tear down: `./scripts/teardown.sh --profile <YOUR_AWS_PROFILE>`

## Architecture Decisions

The [docs/adr/](docs/adr/) directory contains 11 Architecture Decision Records:

| ADR | Decision | Rationale |
|-----|----------|-----------|
| [001 — Programming Language](docs/adr/001-programming-language.md) | Python 3.12+ | Native support across Strands, dbt, and Streamlit |
| [002 — LLM Provider](docs/adr/002-llm-provider.md) | Amazon Bedrock (Claude Sonnet 4 / Opus 4) | Data stays in AWS, IAM auth, native Strands integration |
| [003 — Deployment Environment](docs/adr/003-deployment-environment.md) | Bedrock AgentCore Runtime | Serverless agent hosting, session isolation |
| [004 — Agent Framework](docs/adr/004-agent-framework.md) | Strands Agents SDK | Minimal boilerplate, `@tool` decorator |
| [005 — Demo Database](docs/adr/005-demo-database.md) | RDS PostgreSQL 16 + Northwinds | Fast provisioning, universal familiarity |
| [006 — Data Connectivity](docs/adr/006-data-connectivity-layer.md) | Hybrid Toolkit CLI + psycopg2 | Rich metadata + structured results |
| [007 — Serving Pattern](docs/adr/007-agentcore-serving-pattern.md) | Custom AG-UI adapter | Thin bridge, auto-discovers schema |
| [008 — FAST Integration](docs/adr/008-fast-integration.md) | FAST template with Terraform | Three-module hierarchy, production-grade infra |
| [009 — Multi-Database](docs/adr/009-multi-database-abstraction.md) | DatabaseDriver protocol | One file per DB, optional deps, consistent API |
| [010 — Gateway Routing](docs/adr/010-agentcore-gateway-tool-routing.md) | Hybrid: 5 Lambda + 2 direct tools | Independent tool scaling, filesystem access for dbt |
| [011 — Observability](docs/adr/011-agentcore-observability.md) | OTel auto-instrumentation | CloudWatch Traces, custom spans optional |

## Agent Capabilities

The agent exposes 8 tools to the LLM:

1. **`connect_to_database`** — Connect to PostgreSQL or Redshift (via `driver_type` parameter)
2. **`scan_metadata`** — Discover tables, columns, constraints, relationships, row counts
3. **`profile_database`** — Column-level statistics (cardinality, nulls, distributions)
4. **`run_query`** — Execute read-only SQL and return structured results
5. **`execute_ddl`** — Run DDL statements (DROP/TRUNCATE blocked by guardrails)
6. **`generate_dbt_project`** — Full dbt project from a star schema design (adapter auto-selected)
7. **`generate_semantic_layer`** — MetricFlow YAML for the dbt Semantic Layer

## Multi-Database Support

| Database | Driver | Install | dbt Adapter | Status |
|----------|--------|---------|-------------|--------|
| PostgreSQL | psycopg2 | (included) | dbt-postgres | Supported |
| Redshift | redshift_connector | `uv pip install -e ".[redshift]"` | dbt-redshift | Supported |
| Snowflake | snowflake-connector-python | `uv pip install -e ".[snowflake]"` | dbt-snowflake | Planned |
| Databricks | databricks-sql-connector | `uv pip install -e ".[databricks]"` | dbt-databricks | Planned |

Adding a new database: create one driver file in `src/platform_agent/drivers/`, register it, add the connector dependency. All tools, Gateway Lambda, and dbt generation work automatically.

## Development

```bash
uv pip install -e ".[dev]"              # Install core deps
uv pip install -e ".[redshift]"         # Add Redshift driver
uv run pytest                           # Run tests
uv run ruff check src/ tests/ patterns/ # Lint
uv run ruff format src/ tests/ patterns/ # Format

# Terraform
cd infra-terraform && terraform init && terraform plan

# Docker (local dev)
cd docker && docker-compose up --build
```

## dbt Project (Northwinds)

Generated dbt project: 8 staging models, 6 marts (1 fact + 5 dimensions), 12 tests, 8 sources.

```bash
uv run dbt deps  --project-dir dbt_output/northwinds_dw --profiles-dir dbt_output/northwinds_dw
uv run dbt run   --project-dir dbt_output/northwinds_dw --profiles-dir dbt_output/northwinds_dw
```
