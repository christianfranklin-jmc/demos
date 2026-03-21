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
docs/adr/                     # Architecture Decision Records (6 ADRs)
tests/                        # Unit and integration tests
streamlit_app/                # Streamlit TTYD application (Phase 5)
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

Next phases:
- **Phase 3**: Interactive discovery (NL Q&A over database metadata)
- **Phase 4**: Dimensional model design + dbt code generation
- **Phase 5**: Semantic layer + Streamlit TTYD app
- **Phase 6**: AgentCore deployment
