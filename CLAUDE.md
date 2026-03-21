# AWS Platform Agent

AI-powered data engineering agent that automates the journey from raw database schema to a working, queryable data product on AWS.

## Tech Stack

- **Language**: Python 3.12+
- **Agent Framework**: Strands Agents SDK (`strands-agents`)
- **LLM**: Amazon Bedrock — Claude Sonnet 4 (default), Opus 4 (complex tasks)
- **Deployment**: Amazon Bedrock AgentCore Runtime
- **Data Layer**: phData Toolkit CLI (`~/toolkit-cli-0.90.0/toolkit`) + psycopg2
- **Transforms**: dbt-postgres
- **Frontend**: Streamlit (Talk To Your Data app)
- **Package Manager**: uv (not pip)

## Directory Layout

```
src/platform_agent/           # Agent source code
  agent.py                    # Strands Agent factory — create_agent()
  models.py                   # BedrockModel config (Sonnet 4, Opus 4)
  __main__.py                 # Interactive CLI entry point
  prompts/system.py           # System prompt (7 capabilities + guardrails)
  tools/
    _toolkit_client.py        # Adapter: Toolkit CLI for scan/profile, psycopg2 for query/DDL
    toolkit_connect.py        # @tool connect_to_database
    toolkit_scan.py           # @tool scan_metadata, profile_database
    toolkit_query.py          # @tool run_query (read-only SQL)
    toolkit_ddl.py            # @tool execute_ddl (DROP/TRUNCATE blocked)
    dbt_generate.py           # @tool generate_dbt_project (star schema → dbt)
    semantic_layer.py         # @tool generate_semantic_layer (MetricFlow YAML)
docs/adr/                     # Architecture Decision Records (6 ADRs)
dbt_output/northwinds_dw/     # Generated dbt project (14 models, compiles clean)
tests/                        # Unit and integration tests
streamlit_app/app.py          # Streamlit TTYD app — schema discovery on connect, NL Q&A
scripts/seed_northwinds.sql   # Northwinds dataset SQL
toolkit.conf                  # phData Toolkit config (Northwinds RDS datasource)
```

## Development Commands

```bash
uv venv && uv pip install -e ".[dev]"   # Setup
source .venv/bin/activate                # Activate
pytest                                   # Run tests
ruff check src/ tests/                   # Lint
ruff format src/ tests/                  # Format
```

## Running the Agent

```bash
# Interactive CLI
source .venv/bin/activate
python -m platform_agent --profile AdministratorAccess-637119802057

# Programmatic
from platform_agent.agent import create_agent
agent = create_agent(profile_name="AdministratorAccess-637119802057")
result = agent("Connect to Northwinds and scan it")
```

## AWS Environment

- **Account**: 637119802057
- **Profile**: `AdministratorAccess-637119802057`
- **Region**: us-east-1
- **RDS**: `platform-agent-northwinds.ciz4texnlef4.us-east-1.rds.amazonaws.com`
  - PostgreSQL 16.6, db.t3.micro, database: `northwinds`, user: `postgres`
  - Northwinds loaded: 14 tables, 830 orders
- **VPC**: vpc-0403b2ad6b468adb3 (phdata-dev-vpc)
- **Bedrock models**: us.anthropic.claude-sonnet-4, us.anthropic.claude-opus-4

## Coding Conventions

- Type hints on all function signatures
- Docstrings on all `@tool` functions (they become LLM-visible descriptions)
- `ruff` for linting and formatting (line length: 99)
- One tool per file in `src/platform_agent/tools/`
- Tests mirror source structure: `tests/unit/`, `tests/integration/`

## Build Progress

Phases completed:
- **Phase 0**: Project scaffold + ADR log
- **Phase 1**: Core Strands agent with Bedrock round-trip
- **Phase 2**: Toolkit integration (5 tools, tested E2E against Northwinds)
- **Phase 3**: Interactive discovery — system prompt enhanced with Discovery Guide, Dimensional Modeling Guide, dbt Standards, and Guardrails
- **Phase 4**: dbt code generation — `generate_dbt_project` tool produces full dbt project (sources, staging, marts, packages.yml with dbt_utils, schema tests). Northwinds star schema: 8 staging models, 6 marts (fct_order_lines + 5 dims), compiles clean

- **Phase 5**: Semantic layer tool (`generate_semantic_layer` — MetricFlow YAML) + Streamlit TTYD app (schema discovery on connect, NL Q&A with auto-charting). Agent learns schema dynamically — no hardcoded database knowledge.

Next phases:
- **Phase 6**: AgentCore deployment

## dbt Project (Northwinds)

```bash
# Compile / run the generated dbt project
cd dbt_output/northwinds_dw
uv run dbt deps --profiles-dir .     # Install dbt_utils
uv run dbt compile --profiles-dir .  # Verify (14 models, 12 tests, 8 sources)
uv run dbt run --profiles-dir .      # Materialize to RDS
```

Note: `profiles.yml` currently has direct credentials for testing. The `generate_dbt_project` tool produces env_var-based profiles by default.

## Streamlit App (Talk To Your Data)

```bash
uv run streamlit run streamlit_app/app.py --server.port 8501
```

The app connects to any PostgreSQL database, runs `scan_metadata` to discover the schema, then accepts NL questions. The agent uses `run_query` to answer with actual data. Results are shown as tables + auto-generated bar charts.
