# AWS Platform Agent

AI-powered data engineering agent that automates the journey from raw database schema to a working, queryable data product on AWS.

## Tech Stack

- **Language**: Python 3.12+
- **Agent Framework**: Strands Agents SDK
- **LLM**: Amazon Bedrock (Claude Sonnet 4 default, Opus 4 for complex tasks)
- **Deployment**: Amazon Bedrock AgentCore Runtime
- **Data Layer**: phData Toolkit (database connectivity and profiling)
- **Transforms**: dbt (data build tool)
- **Frontend**: Streamlit (Talk To Your Data app)

## Directory Layout

```
src/platform_agent/       # Agent source code
  agent.py                # Strands Agent factory
  models.py               # BedrockModel configuration
  prompts/                # System prompt constants
  tools/                  # @tool functions (Toolkit wrappers, profiling, dbt, semantic)
docs/adr/                 # Architecture Decision Records
tests/                    # Unit and integration tests
streamlit_app/            # Streamlit TTYD application
scripts/                  # Database seed scripts
infra/                    # CDK / CloudFormation (future)
```

## Development Commands

```bash
pip install -e ".[dev]"          # Install with dev dependencies
pip install -e ".[dev,agentcore]" # Include AgentCore SDK
pytest                           # Run tests
ruff check src/ tests/           # Lint
ruff format src/ tests/          # Format
```

## Running the Agent

```bash
# Local (requires AWS credentials with Bedrock access)
python -m platform_agent

# Local with AgentCore dev server
agentcore dev
```

## Coding Conventions

- Type hints on all function signatures
- Docstrings on all `@tool` functions (they become LLM-visible descriptions)
- `ruff` for linting and formatting (line length: 99)
- One tool per file in `src/platform_agent/tools/`
- Tests mirror source structure: `tests/unit/`, `tests/integration/`

## AWS Prerequisites

- AWS SSO configured (`aws sso login`)
- Bedrock Claude model access enabled in target region
- RDS PostgreSQL with Northwinds dataset for testing (see `scripts/seed_northwinds.sql`)
