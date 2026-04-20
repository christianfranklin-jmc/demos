# DSA Platform

Combined repo — the DSA MVP's polished 4-step data-product UX (React + Vite + Tailwind, dark-first) driven by real AI agents from the AWS Platform Agent (Python + Strands + Bedrock). Built for phData solution architects running live customer demos and discovery sessions.

**What it does**: connect to a real database → walk through **Requirements → Conceptual Model → Logical Model → Detailed Spec** → download a runnable dbt project scaffolded from actual customer tables. Three source types (PostgreSQL, Redshift, Snowflake with SSO). Offline demo mode for network-constrained rooms.

> Upstream histories preserved: `src/platform_agent/*` came from PlatformAgent; `frontend/*` came from DSA's `feat-enhancements-erd-visuals`. Integration tracked under `specs/001-dsa-agent-integration/` (spec, plan, tasks, contracts) and `docs/adr/015-dsa-agent-integration.md`.

## Quick Start (local, end-to-end)

```bash
# 1. Bootstrap Northwinds PostgreSQL + write .env
./scripts/bootstrap.sh --profile <YOUR_AWS_PROFILE> --services rds
source .env

# 2. Install Python + frontend deps
uv pip install -e ".[dev,redshift,snowflake]"
cd frontend && npm install && cd ..

# 3. Backend: uvicorn on :8080
uv run uvicorn platform_agent.api.app:app --host 0.0.0.0 --port 8080

# 4. Frontend: Vite on :5173
cd frontend && npm run dev

# 5. Walk the 4 steps at http://localhost:5173
```

Streamlit ("Talk to Your Data") still works unchanged:
`uv run streamlit run streamlit_app/app.py --server.port 8501`.

CLI agent: `uv run python -m platform_agent --profile $AWS_PROFILE`.

See `specs/001-dsa-agent-integration/quickstart.md` for the full walkthrough.

## Tech Stack

- **Language**: Python 3.12+
- **Agent Framework**: [Strands Agents SDK](https://github.com/strands-agents/strands-agents)
- **LLM**: Amazon Bedrock — Claude Sonnet 4 (default), Claude Opus 4 (complex tasks)
- **Deployment**: Amazon Bedrock AgentCore Runtime (FAST template, Docker)
- **Infrastructure**: Terraform (three-module hierarchy: amplify-hosting, cognito, backend)
- **Data Layer**: Multi-database `DatabaseDriver` protocol — PostgreSQL, Redshift, Snowflake
- **Migration**: Snowflake → Apache Iceberg (S3/Parquet + Glue Catalog)
- **Transforms**: dbt-postgres, dbt-redshift, dbt-snowflake (driver-selected)
- **dbt MCP**: dbt-labs/dbt-mcp v1.9.3 — 40+ tools for compile, run, test, semantic layer, lineage
- **Gateway**: AgentCore MCP Gateway — data tools + Snowflake tools + Iceberg tools (Lambda)
- **Orchestration**: AWS Step Functions (5-agent pipeline) + EventBridge (steady-state)
- **Observability**: OpenTelemetry auto-instrumentation → CloudWatch Traces
- **Evaluation**: AgentCore evaluators (25 test cases across 5 agents)
- **Auth**: Amazon Cognito (JWT for frontend, OAuth2 M2M for Gateway)
- **Frontend**: React + Vite (agent selector UI) + Streamlit (TTYD app)
- **Package Manager**: uv (not pip)

## Quick Start

```bash
# 1. Bootstrap AWS infrastructure + seed Northwinds data
./scripts/bootstrap.sh --profile <YOUR_AWS_PROFILE>

# 2. Source the generated .env
source .env

# 3. Run the Streamlit app (connects to PostgreSQL, Redshift, or Snowflake)
uv run streamlit run streamlit_app/app.py --server.port 8501

# 4. Or run the agent interactively (CLI)
uv run python -m platform_agent --profile $AWS_PROFILE

# 5. Deploy AgentCore infrastructure
cd infra-terraform
cp terraform.tfvars.example terraform.tfvars
terraform init && terraform apply
```

To tear down: `./scripts/teardown.sh --profile <YOUR_AWS_PROFILE>`

## 5-Agent Architecture (Snowflake → AWS Migration)

Branch `snow-iceberg-migration` implements 5 coordinated agents for autonomous Snowflake → AWS migration:

| Agent | Tools | Role | Verified Against |
|-------|-------|------|------------------|
| **Migration** | 5 | Extract Snowflake schema, generate Iceberg DDL, scaffold dbt project, validate row counts | dbt 9/9 run, 18/18 test pass |
| **Enrichment** | 3 | Generate business descriptions (LLM + RAG), update catalog, build synonym maps | 33 columns described |
| **Quality** | 4 | Generate DQDL rules, run quality checks, dbt test generation, quarantine + remediation | 21 rules, 13 checks PASS |
| **Mapping** | 3 | Extract entities/relationships, generate RDF triples, load Neptune graph | 143 nodes, 793 triples |
| **Query** | 5 | Intent classification, EXPLAIN validation, self-correcting SQL, semantic cache | Top-5 clients query |

**Orchestration**: Step Functions pipeline (Migration → Enrichment → Quality Gate → Parallel[Mapping + Query])

**Tested against**: Pinnacle Financial (`PINNACLE_FINANCIAL_DEMO_ASINGH.ANALYTICS`) — 5 dimensions, 4 fact tables, Snowflake SSO

## Single-Agent Capabilities

The platform agent (branch `redshift-agentcore-dbt`) exposes 8 tools:

1. **`connect_to_database`** — Connect to PostgreSQL, Redshift, or Snowflake
2. **`scan_metadata`** — Discover tables, columns, constraints, relationships, row counts
3. **`profile_database`** — Column-level statistics (cardinality, nulls, distributions)
4. **`run_query`** — Execute read-only SQL and return structured results
5. **`execute_ddl`** — Run DDL statements (DROP/TRUNCATE blocked)
6. **`generate_dbt_project`** — Full dbt project from a star schema design
7. **`generate_semantic_layer`** — MetricFlow YAML for the dbt Semantic Layer

## Multi-Database Support

| Database | Driver | Install | dbt Adapter | Status |
|----------|--------|---------|-------------|--------|
| PostgreSQL | psycopg2 | (included) | dbt-postgres | Supported |
| Redshift | redshift_connector | `uv pip install -e ".[redshift]"` | dbt-redshift | Supported |
| Snowflake | snowflake-connector-python | `uv pip install -e ".[snowflake]"` | dbt-snowflake | Supported |
| Databricks | databricks-sql-connector | `uv pip install -e ".[databricks]"` | dbt-databricks | Planned |

Adding a new database: create one driver file in `src/platform_agent/drivers/`, register it, add the connector dependency. All tools, Gateway Lambda, and dbt generation work automatically.

## Architecture Decisions

The [docs/adr/](docs/adr/) directory contains 14 Architecture Decision Records:

| ADR | Decision |
|-----|----------|
| [001](docs/adr/001-programming-language.md) | Python 3.12+ |
| [002](docs/adr/002-llm-provider.md) | Amazon Bedrock (Claude Sonnet 4 / Opus 4) |
| [003](docs/adr/003-deployment-environment.md) | Bedrock AgentCore Runtime |
| [004](docs/adr/004-agent-framework.md) | Strands Agents SDK |
| [005](docs/adr/005-demo-database.md) | RDS PostgreSQL 16 + Northwinds |
| [006](docs/adr/006-data-connectivity-layer.md) | Hybrid Toolkit CLI + psycopg2 |
| [007](docs/adr/007-agentcore-serving-pattern.md) | Custom AG-UI adapter |
| [008](docs/adr/008-fast-integration.md) | FAST template with Terraform |
| [009](docs/adr/009-multi-database-abstraction.md) | DatabaseDriver protocol |
| [010](docs/adr/010-agentcore-gateway-tool-routing.md) | Hybrid Lambda + direct tools |
| [011](docs/adr/011-agentcore-observability.md) | OTel auto-instrumentation |
| [012](docs/adr/012-multi-agent-orchestration.md) | Step Functions + EventBridge |
| [013](docs/adr/013-snowflake-iceberg-migration.md) | Apache Iceberg on S3 + Glue |
| [014](docs/adr/014-dbt-mcp-integration.md) | dbt MCP Server (40+ tools) |

## Development

```bash
uv pip install -e ".[dev]"              # Install core deps
uv pip install -e ".[snowflake]"        # Add Snowflake driver
uv pip install -e ".[redshift]"         # Add Redshift driver
uv run pytest                           # Run tests
uv run ruff check src/ tests/ patterns/ # Lint
uv run ruff format src/ tests/ patterns/ # Format

# Terraform
cd infra-terraform && terraform init && terraform plan

# Docker (local dev)
cd docker && docker-compose up --build

# dbt (Northwinds on PostgreSQL)
uv run dbt deps  --project-dir dbt_output/northwinds_dw --profiles-dir dbt_output/northwinds_dw
uv run dbt run   --project-dir dbt_output/northwinds_dw --profiles-dir dbt_output/northwinds_dw

# dbt (Pinnacle Financial on Snowflake)
uv run dbt deps  --project-dir dbt_output/pinnacle_dw --profiles-dir dbt_output/pinnacle_dw
uv run dbt run   --project-dir dbt_output/pinnacle_dw --profiles-dir dbt_output/pinnacle_dw
```
