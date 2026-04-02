<!--
Sync Impact Report
- Version change: 2.0.0 → 2.1.0 (MINOR — dark mode + backend indicator)
- Modified: Article V — added dark-first default, dark surface colors,
  backend mode visibility requirement
- Previous: 1.1.0 → 2.0.0 (MAJOR — complete restructure)
- Restructured from 8 numbered principles to 10 Articles + Project Addenda
- Old → New mapping:
  - I. CLAUDE.md as Source of Truth → Preamble (preserved)
  - II. Driver-Abstracted Data Access → Addendum A
  - III. Tool-Per-File → absorbed into Article VII
  - IV. Human-in-the-Loop → absorbed into Article VI + Addendum C
  - V. Infrastructure as Code → Addendum D
  - VI. Kimball Methodology → Addendum B
  - VII. Observability → Addendum E
  - VIII. Simplicity → absorbed into Article X
- Added sections: Articles I–X (universal), Project Addenda A–E
- Removed sections: Technology Constraints, Development Workflow
  (absorbed into articles and CLAUDE.md)
- Templates requiring updates:
  - plan-template.md ✅ no update needed (Constitution Check is generic)
  - spec-template.md ✅ no update needed
  - tasks-template.md ✅ no update needed
  - commands/ ✅ no command files exist
- Follow-up TODOs:
  - mypy strict not yet enforced in current codebase (Article III)
  - Pydantic models not yet used for all data boundaries (Article III)
  - phData brand palette not yet applied to Streamlit app (Article V)
-->

# AWS Platform Agent Constitution

This document defines the non-negotiable principles for all specification,
planning, and implementation phases. The AI agent MUST consult and adhere
to these constraints before generating any artifact, plan, or code.

**Preamble — CLAUDE.md as Source of Truth:**
All AI agents and assistants working in this repository MUST read
`CLAUDE.md` at the project root before taking any action and MUST follow
its instructions completely. `CLAUDE.md` contains the authoritative
current state, tech stack, directory layout, development commands, and
coding conventions. When `CLAUDE.md` conflicts with other documentation,
`CLAUDE.md` wins.

---

## Article I — Language & Runtime Philosophy

**Python is the default language for everything that is not a frontend.**

- If the deliverable involves a UI rendered in a browser, use React 18 +
  TypeScript (see Article II).
- If the deliverable is anything else — backend, API, CLI, agent, data
  pipeline, script, automation, infrastructure tooling — **use Python**.
- Do not introduce Go, Rust, Node.js, Java, or any other backend language
  unless the spec explicitly requires it and a technical justification is
  provided. Even then, confirm with the developer before proceeding.
- **`uv` is the mandatory Python package and environment manager.** Never
  use `pip install` directly, `poetry`, `pipenv`, `conda`, or `venv`
  alone. All dependency management goes through `uv`.

### uv Conventions (non-negotiable)

```bash
# Start every Python project with:
uv init my-project
cd my-project

# Add dependencies:
uv add fastapi anthropic boto3

# Add dev dependencies:
uv add --dev pytest ruff mypy

# Run scripts:
uv run python main.py
uv run pytest

# Never do this:
pip install anything       # WRONG
python -m venv .venv       # WRONG (uv manages this)
poetry add anything        # WRONG
```

- `pyproject.toml` is the single source of truth for all project metadata
  and dependencies. No `requirements.txt` unless a downstream tool
  explicitly requires it (e.g., a Docker base image with no uv support).
- Lock files (`uv.lock`) MUST be committed to the repository.

---

## Article II — Frontend Stack (when a UI is required)

*Only applicable when the spec calls for a browser-rendered interface.*

- **React 18, TypeScript (strict mode), Vite, Tailwind CSS** for new
  browser UIs.
- Tailwind core utility classes only — no custom plugins or purge-unsafe
  dynamic class generation.
- State management: React Context + useReducer. No Redux, Zustand, or
  other third-party state libraries unless explicitly spec'd.
- No inline styles. All styling through Tailwind or CSS custom properties.
- **Claude API calls MUST never be made directly from the browser.**
  Route through a Python backend (FastAPI preferred) or a Vite proxy.

**Current project note:** Streamlit is the primary demo frontend today
(`streamlit_app/app.py`). A React + Vite + shadcn/ui frontend exists
under `frontend/` but is scaffolded, not yet connected to a running
backend. New browser UIs follow the React/TypeScript standard above;
Streamlit remains valid for rapid prototyping and internal demos.

---

## Article III — Python Best Practices (non-negotiable)

- **Type hints everywhere.** Every function signature — parameters and
  return types — MUST be fully annotated. No bare `def f(x):`.
- **Pydantic for all data models.** Any structured data that crosses a
  boundary (API request/response, config, agent I/O) MUST be a Pydantic
  `BaseModel`. No raw dicts as function contracts.
- **`ruff` for linting and formatting.** Configured in `pyproject.toml`.
  Code MUST pass `uv run ruff check .` and `uv run ruff format .` before
  a task is considered complete.
- **`mypy` for static type checking.** MUST pass `uv run mypy .` in
  strict mode. Add to `pyproject.toml`:
  ```toml
  [tool.mypy]
  strict = true
  ```
- **No mutable default arguments.** Use `None` and assign inside the
  function body.
- **Explicit over implicit.** No magic. No monkey-patching. No global
  state mutation outside of clearly marked singletons.
- **`pathlib.Path` over `os.path`.** Always.
- **`logging` over `print`.** All runtime output goes through Python's
  standard `logging` module with named loggers. `print()` is only
  acceptable in CLI entry points as final user output.
- **Environment variables via `python-dotenv` or `pydantic-settings`.**
  Never hardcode secrets or config values. Load from `.env`.
- **`__init__.py` files MUST be intentional.** Do not auto-create them
  everywhere — only where the package boundary is real.

### Project Structure (standard Python layout)

```
my-project/
├── pyproject.toml          # uv-managed, single source of truth
├── uv.lock                 # committed
├── .env.example            # all required keys, values redacted
├── README.md
├── src/
│   └── my_project/
│       ├── __init__.py
│       ├── main.py         # entry point
│       ├── models.py       # Pydantic models
│       ├── config.py       # pydantic-settings config
│       ├── agents/         # agent logic
│       ├── tools/          # agent tools / MCP integrations
│       └── api/            # FastAPI routes (if applicable)
└── tests/
    └── test_*.py
```

---

## Article IV — AI / LLM Stack

- **Anthropic Python SDK** (`anthropic`) is the default LLM client for
  direct API access.
- **Model:** `claude-sonnet-4-6` as default. Use `claude-opus-4-6` for
  complex reasoning tasks. No other model strings without explicit spec
  override.
- **AWS Bedrock** when the project requires cloud-hosted inference —
  use `boto3` with the Bedrock runtime client.
- **Strands Agents SDK** (`strands-agents`) for the agent framework when
  building multi-step or multi-agent systems on AWS.
- **Amazon AgentCore** for hosting agents in production AWS deployments.
- System prompts live in dedicated files under `src/prompts/` or
  `src/agents/prompts/`. They are never inline strings in application
  code.
- Every Claude API call MUST be wrapped in try/except with typed error
  handling for `anthropic.APIError` and its subclasses.

---

## Article V — Design & Brand

- **Dark mode is the default.** All UIs MUST be designed dark-first.
  Light mode is optional and secondary.
- **phData brand palette is mandatory** for all visual output:
  - Navy `#1B2A4A`, Blue `#2563EB`, Teal `#0D9488`, Orange `#F97316`
  - Dark surfaces: `#0F172A` (background), `#1E293B` (cards/panels)
  - Text: `#F1F5F9` (primary), `#94A3B8` (secondary)
- **No off-brand colors** without an explicit spec instruction.
- **Typography:** Inter or system-ui. No decorative fonts.
- **UI MUST feel enterprise-grade** — credible, minimal chrome, high
  contrast. Not playful or consumer-casual.
- **Backend mode MUST be visible.** When an agent UI supports multiple
  backends (local agent vs AgentCore Runtime), the active mode MUST be
  clearly indicated to the user.
- **Layout stability:** Panels and sidebars do not resize in response to
  content. Widths are defined in the spec and are fixed.
- **Empty states MUST be meaningful.** Explain what will appear and when.
  "No data" is never acceptable.

---

## Article VI — Agent & Conversational UX Rules

*Applies to any product that embeds a conversational AI agent.*

1. **One question at a time. Always.** No compound or multi-part questions
   in a single turn. Ever.
2. **The artifact is the source of truth.** The chat is conversation; the
   artifact is the product. What appears in the artifact is what persists.
3. **Human gates are deliberate moments.** Gates block progression until
   explicit human approval. They are not toasts or dismissible dialogs.
4. **Agent personas are step-scoped.** No cross-step context bleed. Each
   step gets its own system prompt and identity.
5. **The agent never generates beyond the current step.** No speculation
   about future steps or references to prior artifacts unless explicitly
   injected via context.

---

## Article VII — Code Quality & Architecture

- **Separation of concerns is mandatory.** Business logic, I/O, and
  presentation layers are always in separate modules.
- **No secrets in source.** All credentials go in `.env`. `.env.example`
  is committed with all required variable names (values redacted).
- **Functions do one thing.** If a function exceeds ~40 lines, it is a
  signal to decompose.
- **One tool per file.** Each agent tool lives in its own file with a
  docstring that serves as the LLM-visible description. Tools are the
  agent's only interface to external systems — no side-channel access.
- **Mock data MUST be realistic.** Domain-accurate field names, plausible
  values, data that tells a coherent story for the demo scenario. No
  Lorem Ipsum, no `foo`/`bar`.
- **Error states MUST be handled.** All async operations and API calls
  have try/except with graceful degradation. A demo that crashes on a
  network error is unacceptable.

---

## Article VIII — Demo & Delivery Standards

- **Every demo MUST have a scripted moment.** If a feature cannot be
  demonstrated live in under 3 minutes, the scope is too large or the
  UX is too complex.
- **Loading and error states MUST be visible.** No layout shift after
  load. No silent failures.
- **Every project MUST have a `PLAN.md`** at the root describing what
  exists, the build order, and the non-negotiable constraints — written
  for a coding agent reading it cold.
- **`README.md` MUST include:** setup commands using `uv`, env var
  requirements, and a 3-sentence description of what the app does and
  for whom.

---

## Article IX — Testing Philosophy

- **`pytest` is the only test framework.** Configured in `pyproject.toml`.
- **Unit tests are not required for demo-scoped MVPs** unless the spec
  calls for them.
- **Critical path tests are required** for any feature handling data
  persistence or external API calls in a production-bound project.
- **Type safety is the first line of defense.** `mypy` strict + `ruff`
  catch a significant class of bugs before runtime. Lean on them.

---

## Article X — Scope Discipline

- **Build what the spec says. Nothing more.**
- If a "nice to have" is not in the spec, do not implement it. Leave a
  `# TODO(future):` comment instead.
- **Architectural decisions not covered by this constitution** MUST be
  surfaced to the developer for approval — never silently defaulted.
- **When in doubt, do less.** A smaller, working, well-designed feature
  is worth more than a larger, half-finished one.
- **Python over everything.** If you are about to reach for a non-Python
  tool for a non-frontend task, stop and ask first.

---

## Project Addenda — AWS Platform Agent

*These rules extend the universal articles above with constraints
specific to this repository.*

### Addendum A — Driver-Abstracted Data Access

All database interactions go through the `DatabaseDriver` protocol
(`src/platform_agent/drivers/base.py`). No tool or service directly
imports a database connector. New databases are added by implementing a
single driver file — tools, Gateway Lambda, and dbt generation work
automatically. This ensures the agent is database-agnostic by design.

### Addendum B — Kimball Methodology for Modeling

Dimensional models follow Kimball star-schema conventions: `fct_` and
`dim_` prefixes, surrogate keys via `dbt_utils.generate_surrogate_key()`,
explicit grain documentation, conformed dimensions. dbt projects use
CTE-based SQL, `ref()`/`source()` references, and staging-to-marts
layering.

### Addendum C — Agent Guardrails

- The agent operates in read-only mode by default. Write operations
  (DDL, dbt materialization) require explicit human approval.
- Dimensional model designs MUST be presented and approved before any
  code generation.
- DROP, TRUNCATE, and ALTER on source tables are unconditionally blocked.
- Each session is scoped to a single database or catalog.
- Always cite specific `table.column` references; verify claims with
  `run_query` when possible.
- When uncertain, say so and suggest a query to resolve ambiguity.

### Addendum D — Infrastructure as Code

All AWS resources are defined in Terraform (`infra-terraform/`
three-module hierarchy) or provisioned by idempotent bootstrap scripts.
No manual console changes. Environment config flows through `.env`, SSM
parameters, or Secrets Manager — never hardcoded.

### Addendum E — Observability and Traceability

Every architectural decision is recorded as an ADR in `docs/adr/`.
Agent runtime uses OpenTelemetry auto-instrumentation to CloudWatch
Traces. Evaluation uses AgentCore built-in evaluators (on-demand +
online sampling).

---

## Governance

This constitution captures the binding architectural and behavioral
principles for all projects in this workspace. It supersedes ad-hoc
conventions. Amendments follow this procedure:

1. Propose the change with rationale and alternatives considered.
2. Record an ADR in `docs/adr/` documenting the decision.
3. Update this file with a version bump per semantic versioning:
   - **MAJOR**: Principle removals or backward-incompatible redefinitions.
   - **MINOR**: New principles/sections added or materially expanded.
   - **PATCH**: Clarifications, wording, typo fixes.
4. Update `CLAUDE.md` if the change affects current-state documentation.
5. Verify dependent templates (plan, spec, tasks) remain consistent.

**Version**: 2.1.0 | **Ratified**: 2026-04-01 | **Last Amended**: 2026-04-01
