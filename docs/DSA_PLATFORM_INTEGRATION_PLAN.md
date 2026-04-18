# dsa-platform Integration Plan

> This document is a complete handoff for a new Claude Code session to create the `dsa-platform` repo by combining two existing repos. Read this fully before writing any code.

## What We're Building

A new repo (`dsa-platform`) that combines:
- **DSA MVP** (`/Users/mwebb/Projects/dsa-mvp`) — Polished React frontend with a 4-step agent-driven data product workflow (requirements → conceptual model → logical model → detailed spec). Currently uses pre-scripted interview flows.
- **PlatformAgent** (`/Users/mwebb/Projects/PlatformAgent_1`) — Python backend with AI agents that connect to real databases (PostgreSQL, Redshift, Snowflake), discover schemas, design dimensional models, generate dbt projects. Deployed to AWS AgentCore.

**The integration:** DSA's React UI drives PlatformAgent's real agent backend. The 4-step DSA workflow calls PlatformAgent tools at each step instead of pre-scripted responses.

**Uses Speckit** (`.specify/`) for structured planning.

---

## Source Repos — Current State

### PlatformAgent_1 (`/Users/mwebb/Projects/PlatformAgent_1`)
- **Remote:** `git@bitbucket.org:phdata/aws-mw-platform-agents.git`
- **Branches:**
  - `main` — Single-agent, fully deployed (AgentCore Runtime, Gateway, Memory, Cognito, Amplify)
  - `snow-iceberg-migration` — 5-agent architecture (Migration, Enrichment, Quality, Mapping, Query). 10 commits ahead of main. NOT merged.
  - `redshift-agentcore-dbt` — Merged into main already.

#### Main Branch Key Files
```
src/platform_agent/           # Python agent source
  agent.py                    # Strands Agent factory — create_agent()
  models.py                   # BedrockModel (Sonnet 4, Opus 4)
  __main__.py                 # CLI entry point
  serve.py                    # AgentCore Runtime (AG-UI protocol)
  drivers/                    # DatabaseDriver protocol + PostgreSQL, Redshift
    base.py, __init__.py, postgresql.py, redshift.py
  tools/                      # 7 @tool functions
    toolkit_connect.py, toolkit_scan.py, toolkit_query.py, toolkit_ddl.py
    dbt_generate.py, semantic_layer.py, _toolkit_client.py
  prompts/system.py           # System prompt (7 capabilities + guardrails)
patterns/platform-agent/      # FAST AgentCore container pattern
  agent.py                    # BedrockAgentCoreApp + @app.entrypoint
  Dockerfile                  # arm64, OTel instrumentation
patterns/utils/               # JWT auth + SSM helpers
infra-terraform/              # Terraform (Cognito, Runtime, Gateway, Memory, Amplify)
  modules/backend/            # runtime.tf, gateway.tf, memory.tf, auth.tf, ssm.tf
  modules/cognito/            # User Pool + OAuth2 clients
  modules/amplify-hosting/    # S3 + Amplify App
gateway/tools/data_tools/     # Lambda handler (5 data tools)
frontend/                     # React + Vite + Tailwind (basic scaffold)
  src/App.tsx                 # Basic chat UI with DB connection sidebar
  src/lib/agentcore-client/   # SSE streaming client (5 parsers)
  src/lib/auth.ts             # Cognito PKCE auth
streamlit_app/app.py          # Streamlit TTYD app (primary demo today)
scripts/bootstrap.sh          # Modular: --services rds,redshift,snowflake,terraform,all
scripts/teardown.sh           # Matching --services flag
eval/                         # Evaluation framework
dbt_output/northwinds_dw/     # PostgreSQL dbt project (14 models)
docs/adr/                     # 14 ADRs
```

#### Snow-Iceberg-Migration Branch (10 commits ahead of main)
```
src/platform_agent/drivers/snowflake.py    # SnowflakeDriver (SSO/externalbrowser)
patterns/migration-agent/                   # Extract → Iceberg → Glue → dbt
  tools/extract_schema.py, convert_to_iceberg.py, validate_migration.py
patterns/enrichment-agent/                  # RAG + DataZone + semantic YAML
  tools/generate_descriptions.py, enrich_catalog.py
patterns/quality-agent/                     # DQDL + quarantine + dbt test
  tools/quality_rules.py, quarantine.py
patterns/mapping-agent/                     # Neptune graph + entity extraction
  tools/knowledge_graph.py
patterns/query-agent/                       # NL-to-SQL + semantic cache
  tools/semantic_query.py, cache.py
gateway/tools/snowflake_tools/              # Lambda: extract_semantic_metadata, validate_row_counts
gateway/tools/iceberg_tools/                # Lambda: convert_to_iceberg, export_data, register_glue_catalog
gateway/mcp/dbt-mcp-config.json             # dbt MCP server config
infra-terraform/modules/data/               # S3, Glue, Neptune, ElastiCache
infra-terraform/modules/secrets/            # Secrets Manager
infra-terraform/modules/events/             # EventBridge + Step Functions
eval/test_cases/                            # Per-agent evaluation
dbt_output/pinnacle_dw/                     # Snowflake dbt project (9 models, all pass)
docs/adr/012-014                            # Multi-agent, Iceberg, dbt MCP ADRs
```

### DSA MVP (`/Users/mwebb/Projects/dsa-mvp`)
- **Remote:** `git@bitbucket.org:phdata/data-services-accelerator.git`
- **Branches:**
  - `main` — Working 4-step demo with pre-scripted agent. 9 commits.
  - `feat-enhancements-erd-visuals` — **UNMERGED, INCLUDE THIS.** Removes 2158 lines, adds 508 lines. Simplifies ConceptualERD, removes OpenQuestionsView, trims useAgent.ts from ~1000 to ~300 lines.
  - `feature/combined-enhancements` — Already merged into main.

#### Main Branch Key Files (include feat-enhancements-erd-visuals changes)
```
src/
  App.tsx                           # Shell layout
  main.tsx                          # React entry
  hooks/useAgent.ts                 # Conversation engine (~1000 lines on main, ~300 on branch)
  context/AppContext.tsx            # 23 reducer actions
  context/ThemeContext.tsx           # Runtime theme (4 presets: Sana, phData, Dark, Minimal)
  components/
    shell/AppShell.tsx, Sidebar.tsx, ContextBar.tsx
    chat/ChatPanel.tsx, MessageBubble.tsx, ChatInput.tsx, SuggestedReplies.tsx
    artifact/ArtifactPanel.tsx, PRDView.tsx, ConceptualERD.tsx, LogicalModel.tsx
    artifact/DetailedRequirements.tsx, GraphView.tsx, TabBar.tsx, EditableCell.tsx
    gates/GateApproval.tsx
    shared/EmptyState.tsx, StatusPill.tsx, SettingsPanel.tsx
  lib/
    types.ts                        # All TypeScript interfaces
    constants.ts                    # Step/gate/flag config, Snowflake catalog
    scoring.ts                      # PRD completeness scoring
    specExport.ts                   # Spec + dbt YAML generators (REMOVED in branch)
    validation.ts                   # Standards validation engine
    theme-config.ts                 # Theme system
    claude.ts                       # Claude API client wrapper
  data/
    prompts/                        # System prompts per step
    standards.ts                    # Enterprise standards rules
    mock/                           # Atlan, Snowflake, Highspot, data-products
docs/
  DESIGN_SPEC.md, DEMO_REQUIREMENTS.md, ROMI_PRD.md, ROMI_DETAILED_REQUIREMENTS.md
```

#### Dependencies
```json
{
  "dependencies": { "@xyflow/react": "^12", "react": "^18", "react-dom": "^18" },
  "devDependencies": { "tailwindcss": "^4", "typescript": "^5.6", "vite": "^6" }
}
```

---

## Target: dsa-platform Repo Structure

```
dsa-platform/
├── .specify/                          # Speckit (constitution, specs, plans, tasks)
│   └── memory/constitution.md
├── CLAUDE.md                          # Combined project instructions
├── frontend/                          # DSA React app (from dsa-mvp)
│   ├── src/
│   │   ├── hooks/useAgent.ts          # REWRITTEN: calls PlatformAgent API instead of pre-scripted
│   │   ├── context/AppContext.tsx      # Extended with database connection state
│   │   ├── components/                # All DSA components (shell, chat, artifact, gates)
│   │   ├── lib/
│   │   │   ├── agentcore-client/      # FROM PlatformAgent: SSE streaming client
│   │   │   ├── auth.ts               # FROM PlatformAgent: Cognito PKCE auth
│   │   │   ├── types.ts              # DSA types + PlatformAgent types merged
│   │   │   ├── theme-config.ts       # DSA theme system (preserved)
│   │   │   └── ...                   # Other DSA libs
│   │   └── data/                     # DSA prompts, standards, mock data
│   ├── package.json                   # DSA deps + agentcore-client deps
│   └── vite.config.ts
├── src/platform_agent/                # FROM PlatformAgent: Python agent backend
│   ├── agent.py, models.py, serve.py
│   ├── drivers/                       # PostgreSQL, Redshift, Snowflake
│   ├── tools/                         # 7 @tool functions
│   └── prompts/system.py
├── patterns/                          # FROM PlatformAgent: AgentCore patterns
│   ├── platform-agent/               # Single-agent (main demo)
│   ├── migration-agent/              # FROM snow-iceberg-migration
│   ├── enrichment-agent/             # FROM snow-iceberg-migration
│   ├── quality-agent/                # FROM snow-iceberg-migration
│   ├── mapping-agent/                # FROM snow-iceberg-migration
│   ├── query-agent/                  # FROM snow-iceberg-migration
│   └── utils/                        # Auth + SSM helpers
├── gateway/                           # FROM PlatformAgent: Lambda tools
│   ├── tools/data_tools/
│   ├── tools/snowflake_tools/        # FROM snow-iceberg-migration
│   ├── tools/iceberg_tools/          # FROM snow-iceberg-migration
│   └── mcp/                          # FROM snow-iceberg-migration
├── infra-terraform/                   # FROM PlatformAgent: full Terraform
├── streamlit_app/                     # FROM PlatformAgent: preserved as alternative
├── scripts/                           # FROM PlatformAgent: bootstrap, teardown
├── eval/                              # FROM PlatformAgent: evaluation
├── dbt_output/                        # FROM both: northwinds + pinnacle
├── docs/
│   ├── adr/                          # FROM PlatformAgent: 14 ADRs
│   ├── DESIGN_SPEC.md                # FROM DSA
│   ├── DEMO_REQUIREMENTS.md          # FROM DSA
│   └── ROMI_*.md                     # FROM DSA
├── pyproject.toml                     # FROM PlatformAgent
├── .env.example                       # FROM PlatformAgent (extended)
└── docker/docker-compose.yml          # FROM PlatformAgent (extended)
```

---

## Integration Steps

### Step 1: Create the New Repo
```bash
mkdir /Users/mwebb/Projects/dsa-platform
cd /Users/mwebb/Projects/dsa-platform
git init
```

### Step 2: Pull PlatformAgent (both branches)
```bash
# Add PlatformAgent as a remote
git remote add platform-agent /Users/mwebb/Projects/PlatformAgent_1
git fetch platform-agent

# Merge main as the base
git merge platform-agent/main --allow-unrelated-histories -m "Import PlatformAgent main branch"

# Merge snow-iceberg-migration (the 5-agent work)
git merge platform-agent/snow-iceberg-migration -m "Merge snow-iceberg-migration (5 agents, Snowflake driver)"
# Resolve any conflicts — main has AgentCore deployed, snow-iceberg has 5 agents
```

### Step 3: Pull DSA (main + unmerged branch)
The DSA frontend needs to go into `frontend/` (replacing PlatformAgent's basic React scaffold):

```bash
# Add DSA as a remote
git remote add dsa /Users/mwebb/Projects/dsa-mvp
git fetch dsa

# Create a temporary branch from DSA's unmerged branch (has the latest code)
git checkout -b dsa-import dsa/feat-enhancements-erd-visuals

# Move everything into frontend/ subdirectory
mkdir -p frontend
git mv src/ frontend/src/
git mv public/ frontend/public/
git mv index.html frontend/
git mv package.json frontend/
git mv vite.config.ts frontend/
git mv tsconfig.json frontend/
# Move DSA docs into docs/
git mv docs/* docs/ 2>/dev/null || true
git mv PLAN.md docs/DSA_PLAN.md
git mv CLAUDE_CODE_INSTRUCTIONS.md docs/DSA_INSTRUCTIONS.md
git commit -m "Restructure DSA into frontend/ subdirectory"

# Merge back into main
git checkout main
git merge dsa-import -m "Import DSA frontend (feat-enhancements-erd-visuals branch)"
# Resolve conflicts in frontend/ (DSA replaces PlatformAgent's basic scaffold)
```

### Step 4: Wire DSA Frontend to PlatformAgent Backend

The critical integration point is `frontend/src/hooks/useAgent.ts`. Currently it has pre-scripted flows. It needs to be rewritten to:

1. **Step 1 (Requirements):** Call PlatformAgent's `connect_to_database` + `scan_metadata` to discover the real schema, then use the agent to help define the data product PRD.
2. **Step 2 (Conceptual Model):** Call `scan_metadata` to get tables/FKs, propose entities/relationships from actual database structure.
3. **Step 3 (Logical Model):** Call `run_query` to sample data, map fields with real data types from the source.
4. **Step 4 (Detailed Requirements):** Call `generate_dbt_project` + `generate_semantic_layer` to produce real dbt code.

The frontend communicates with the agent via:
- **Local dev:** HTTP POST to `http://localhost:8080/invocations` (Docker Compose)
- **Deployed:** AgentCore Runtime endpoint via `agentcore-client` SSE streaming with Cognito auth

Key files to modify:
- `frontend/src/hooks/useAgent.ts` — Replace pre-scripted flows with API calls
- `frontend/src/context/AppContext.tsx` — Add database connection state + agent response handling
- `frontend/src/lib/types.ts` — Add PlatformAgent response types (QueryResult, SchemaInfo, etc.)

### Step 5: Speckit Initialization
```bash
# In the new repo
/speckit.constitution    # Create project constitution
/speckit.specify         # Create feature spec for the integration
/speckit.plan            # Generate implementation plan
/speckit.tasks           # Generate task list
```

### Step 6: Update Documentation
- Write new `CLAUDE.md` combining both projects' context
- Write new `README.md`
- Add ADR-015: DSA + PlatformAgent integration decision

---

## AWS Resources (Already Deployed on PlatformAgent main)

| Resource | ID/ARN | Notes |
|----------|--------|-------|
| AgentCore Runtime | `platform_agent_runtime-OfViSJB74e` | arm64 container, 7 tools |
| AgentCore Gateway | `platform-agent-gateway-wwjorrqn4v` | 5 Lambda data tools |
| AgentCore Memory | `platform_agent_memory-3Z2bC62Ztv` | 30-day retention |
| Cognito User Pool | `us-east-1_iQ70gh7t7` | PKCE auth |
| Cognito Web Client | `18nqacih7h0drtth8ghobmlsac` | Admin: mwebb@phdata.io |
| Amplify App | `https://main.d2fj6tk58y0pxw.amplifyapp.com` | React frontend |
| ECR | `637119802057.dkr.ecr.us-east-1.amazonaws.com/platform-agent-agent` | Docker images |
| RDS | `platform-agent-northwinds.ciz4texnlef4.us-east-1.rds.amazonaws.com:5432` | Northwinds |
| Redshift | `platform-agent-wg.637119802057.us-east-1.redshift-serverless.amazonaws.com:5439` | Partially seeded |

## Snowflake (External)

| Property | Value |
|----------|-------|
| Account | lga76011 (PHDATAPARTNER-AWS) |
| User | MWEBB@PHDATA.IO |
| Auth | externalbrowser (SSO) |
| Role | ALL_ML_ARCHITECTS |
| Warehouse | COMPUTE_WH |
| Database | PINNACLE_FINANCIAL_DEMO_ASINGH |
| Schema | ANALYTICS |
| Tables | 9 (5 dims + 4 facts) |

---

## Key Technical Decisions

1. **DSA's theme system is preserved.** The 4 presets (Sana, phData, Dark, Minimal) and runtime configurability stay. PlatformAgent's basic frontend is replaced entirely.

2. **PlatformAgent's agentcore-client replaces DSA's claude.ts.** DSA currently calls Claude API directly for pre-scripted responses. In the combined repo, the frontend calls the PlatformAgent backend (which uses Bedrock internally).

3. **The 4-step workflow stays.** DSA's step/gate structure is the UX framework. PlatformAgent tools are called within each step.

4. **Pre-scripted flows become fallbacks.** For demos without live database connectivity, the pre-scripted responses can still work as a "demo mode" toggle.

5. **Both Streamlit and DSA React are preserved.** Streamlit is the quick local demo. DSA React is the polished production UI.

6. **Python backend stays as-is.** No changes to `src/platform_agent/` — the frontend adapts to the existing API.

---

## Conflict Resolution Guide

When merging, expect conflicts in:
- `frontend/` — PlatformAgent's basic React vs DSA's polished React. **Resolution:** DSA wins for all UI components. Keep PlatformAgent's `agentcore-client/` and `auth.ts`.
- `CLAUDE.md` — Both repos have one. **Resolution:** Write a new one for the combined project.
- `package.json` (frontend) — Different deps. **Resolution:** DSA's deps + add `aws-amplify` from PlatformAgent.
- `docs/` — Both have docs. **Resolution:** Keep both, namespace DSA docs under `docs/dsa/`.

---

## Verification Checklist

After integration, verify:
1. `npm run dev` in `frontend/` — DSA app loads with all 4 steps
2. `uv run streamlit run streamlit_app/app.py` — Streamlit still works
3. `uv run python -m platform_agent` — CLI agent still works
4. `cd infra-terraform && terraform validate` — Terraform still valid
5. `uv run dbt run --project-dir dbt_output/northwinds_dw` — dbt still compiles
6. Frontend connects to PlatformAgent backend — agent responds to real questions
7. Database connection sidebar in DSA UI — connects to RDS/Snowflake
