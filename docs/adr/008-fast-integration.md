# ADR-008: FAST Template Integration with Terraform

**Status**: Accepted

**Date**: 2026-03-26

## Context

The Platform Agent needs production-grade infrastructure: AgentCore Gateway (tool routing), Memory (conversation persistence), Observability (tracing), Evaluation (quality monitoring), authentication (Cognito), and a React frontend. Building this from scratch is significant effort.

AWS published the **Fullstack AgentCore Solution Template (FAST)** at `github.com/awslabs/fullstack-solution-template-for-agentcore` — a reference architecture with both CDK and Terraform implementations, a React frontend, and agent patterns for Strands, LangGraph, and Claude Agent SDK.

## Options Considered

1. **Custom Terraform from scratch** — Full control, but duplicates work FAST already provides (Cognito setup, Amplify hosting, Gateway target wiring, OAuth2 credential provider workaround).
2. **FAST template (Terraform)** — HCL-based, declarative, three-module hierarchy (amplify-hosting, cognito, backend). No Node.js dependency. Uses `null_resource` + local-exec for OAuth2 provider (AgentCore lacks native TF/CFN support).
3. **FAST template (CDK)** — TypeScript, compiles to CloudFormation. More abstracted but requires Node.js toolchain.

## Decision

Adopt the **FAST Terraform path**. We create an `infra-terraform/` directory following FAST's three-module structure, customized for our `platform-agent` pattern. The agent pattern lives in `patterns/platform-agent/` with a Dockerfile for containerized deployment.

**Rationale:**
- HCL is declarative and widely adopted — no transpilation step
- No Node.js/npm dependency for infrastructure
- FAST's three-module hierarchy (amplify-hosting → cognito → backend) maps cleanly to our needs
- Terraform state management (S3 + DynamoDB) is well-established
- The team has Terraform experience

## Consequences

**Positive:**
- Reference architecture for Gateway, Memory, OAuth2, Amplify — no need to figure out IAM policies from scratch
- React frontend with `agentcore-client` SSE streaming library included
- Test scripts for agent, gateway, memory, and feedback testing
- Docker Compose for local development

**Negative:**
- OAuth2 credential provider uses Lambda + `null_resource` local-exec (workaround for missing native TF support) — fragile on re-apply
- Frontend deployment is a separate script (`deploy-frontend.py`), not managed by Terraform
- Must track FAST upstream changes manually (no package manager for TF modules)
- Terraform providers require `>= 6.35.1` for AWS, which includes AgentCore resources
