# AWS Platform Agent

AI-powered data engineering agent that automates the journey from raw database schema to a working, queryable data product on AWS. Connect to any PostgreSQL database, discover its schema, design a dimensional model, generate a full dbt project, add a MetricFlow semantic layer, and query it all through natural language.

## Tech Stack

- **Language**: Python 3.12+
- **Agent Framework**: [Strands Agents SDK](https://github.com/strands-agents/strands-agents)
- **LLM**: Amazon Bedrock — Claude Sonnet 4 (default), Claude Opus 4 (complex tasks)
- **Deployment**: Amazon Bedrock AgentCore Runtime
- **Data Connectivity**: phData Toolkit CLI + psycopg2
- **Transforms**: dbt-postgres
- **Frontend**: Streamlit (Talk To Your Data app)
- **Package Manager**: uv

## Quick Start

```bash
# 1. Bootstrap AWS infrastructure + seed Northwinds data
./scripts/bootstrap.sh --profile AdministratorAccess-637119802057

# 2. Source the generated .env
source .env

# 3. Run the agent interactively
uv run python -m platform_agent --profile $AWS_PROFILE

# 4. Or run the Streamlit app
uv run streamlit run streamlit_app/app.py --server.port 8501
```

To tear down: `./scripts/teardown.sh --profile AdministratorAccess-637119802057`

## Architecture Decisions

The [docs/adr/](docs/adr/) directory contains 7 Architecture Decision Records documenting key technical choices:

| ADR | Decision | Rationale |
|-----|----------|-----------|
| [001 — Programming Language](docs/adr/001-programming-language.md) | Python 3.12+ | Native support across Strands, dbt, and Streamlit; largest data engineering ecosystem |
| [002 — LLM Provider](docs/adr/002-llm-provider.md) | Amazon Bedrock (Claude Sonnet 4 / Opus 4) | Data stays in AWS, IAM auth, native Strands integration |
| [003 — Deployment Environment](docs/adr/003-deployment-environment.md) | Bedrock AgentCore Runtime | Serverless agent hosting, session isolation, no Lambda time limits |
| [004 — Agent Framework](docs/adr/004-agent-framework.md) | Strands Agents SDK | Minimal boilerplate, `@tool` decorator, direct AgentCore deployment |
| [005 — Demo Database](docs/adr/005-demo-database.md) | RDS PostgreSQL 16 + Northwinds | Fast provisioning, universal familiarity, free-tier eligible |
| [006 — Data Connectivity](docs/adr/006-data-connectivity-layer.md) | Hybrid Toolkit CLI + psycopg2 | Rich metadata from Toolkit, structured results from psycopg2 |
| [007 — Serving Pattern](docs/adr/007-agentcore-serving-pattern.md) | Custom AG-UI adapter in `serve.py` | Thin bridge (~100 LOC), works today, auto-discovers schema at runtime |

## Agent Capabilities

The agent exposes 7 tools to the LLM:

1. **`connect_to_database`** — Establish a PostgreSQL connection
2. **`scan_metadata`** — Discover tables, columns, constraints, and relationships
3. **`profile_database`** — Collect column-level statistics (cardinality, nulls, distributions)
4. **`run_query`** — Execute read-only SQL and return results
5. **`execute_ddl`** — Run DDL statements (DROP/TRUNCATE blocked by guardrails)
6. **`generate_dbt_project`** — Produce a full dbt project from a star schema design
7. **`generate_semantic_layer`** — Create MetricFlow YAML for the semantic layer

## Development

```bash
uv pip install -e ".[dev]"      # Install deps
pytest                           # Run tests
ruff check src/ tests/           # Lint
ruff format src/ tests/          # Format
```

## dbt Project (Northwinds)

The generated dbt project lives in `dbt_output/northwinds_dw/` with 8 staging models, 6 marts (1 fact + 5 dimensions), and schema tests.

```bash
uv run dbt deps  --project-dir dbt_output/northwinds_dw --profiles-dir dbt_output/northwinds_dw
uv run dbt run   --project-dir dbt_output/northwinds_dw --profiles-dir dbt_output/northwinds_dw
```

## Jobs To Be Done

- [ ] **Multi-database support** — Extend beyond PostgreSQL to Snowflake, BigQuery, and Redshift
- [ ] **Incremental model generation** — Generate dbt incremental models (not just table/view) for large datasets
- [ ] **Automated testing pipeline** — CI/CD that runs dbt compile + schema tests on every PR
- [ ] **Agent memory / session persistence** — Persist conversation context and discovered schemas across sessions via AgentCore memory APIs
- [ ] **Semantic layer querying** — Wire the generated MetricFlow YAML into dbt Semantic Layer so the agent can query metrics directly
- [ ] **Cost guardrails** — Track and limit Bedrock token usage per session; alert on runaway queries
- [ ] **Multi-tenant isolation** — Support multiple users/databases with proper credential isolation in AgentCore
- [ ] **Observability** — Structured logging, OpenTelemetry traces for tool calls, Bedrock latency dashboards
- [ ] **Data quality checks** — Auto-generate dbt tests (freshness, accepted_values, relationships) from profiling results
- [ ] **Schema change detection** — Detect upstream schema drift and update dbt models accordingly
- [ ] **Production credential management** — Replace `.env` / `toolkit.conf` with AWS Secrets Manager integration
