# Architecture Decision Records

This directory contains Architecture Decision Records (ADRs) for the AWS Platform Agent project.

## What is an ADR?

An ADR is a short document that captures a significant architectural or technical decision, including the context, options considered, and consequences. When an auditor or new team member asks "Why did you choose X?", the answer lives here.

## Index

| ADR | Title | Status | Date |
|-----|-------|--------|------|
| [001](001-programming-language.md) | Programming Language | Accepted | 2026-03-20 |
| [002](002-llm-provider.md) | LLM Provider | Accepted | 2026-03-20 |
| [003](003-deployment-environment.md) | Deployment Environment | Accepted | 2026-03-20 |
| [004](004-agent-framework.md) | Agent Framework | Accepted | 2026-03-21 |
| [005](005-demo-database.md) | Demo Database | Accepted | 2026-03-21 |
| [006](006-data-connectivity-layer.md) | Data Connectivity Layer | Accepted | 2026-03-21 |

## Template

New ADRs should follow this format:

```markdown
# ADR-NNN: Title

**Status**: Proposed | Accepted | Deprecated | Superseded by ADR-NNN

**Date**: YYYY-MM-DD

## Context
What is the issue or requirement that motivates this decision?

## Options Considered
1. **Option A** — Description, pros, cons.
2. **Option B** — Description, pros, cons.

## Decision
What is the chosen option and why?

## Consequences
What are the positive and negative results of this decision?
```
