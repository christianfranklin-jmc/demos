# ADR-003: Deployment Environment

**Status**: Accepted

**Date**: 2026-03-20

## Context

The agent must be deployable as a managed service that handles scaling, authentication, session management, and observability without requiring the team to operate Kubernetes or EC2 infrastructure. The deployment target must support long-running agent sessions (multi-turn conversations with tool calls that may take minutes) and integrate with AWS IAM for security. Sessions range from 30 minutes (demos) to 8 hours (deep work).

## Options Considered

1. **Amazon Bedrock AgentCore Runtime** — Serverless agent hosting with built-in session isolation, memory, gateway, Cedar policy enforcement, and OpenTelemetry observability. Supports Strands Agents natively. Deployment via `agentcore launch` CLI or CDK.
2. **AWS Lambda** — Serverless but 15-minute execution limit and cold start latency are problematic for multi-turn agent sessions with database operations.
3. **Amazon ECS / Fargate** — Full container control but requires managing scaling, health checks, session affinity, and load balancing manually.
4. **Amazon SageMaker Endpoints** — Designed for model inference, not agent orchestration. Misaligned abstraction.

## Decision

Use **Amazon Bedrock AgentCore Runtime** as the production deployment environment, with `agentcore dev` for local development.

## Consequences

- **Positive**: Zero infrastructure management. Built-in session memory, API gateway, and OpenTelemetry observability.
- **Positive**: Native Strands Agents support via `serve_ag_ui()`. AG-UI and A2A protocol support for future multi-agent scenarios.
- **Positive**: `agentcore dev` enables local testing with identical runtime semantics before cloud deployment.
- **Negative**: AgentCore is a relatively new service (GA October 2025); documentation and community knowledge are still growing.
- **Negative**: Region availability is limited (us-east-1, us-west-2, ap-southeast-2, eu-central-1 at launch).
- **Negative**: Vendor lock-in to AWS for the deployment layer, though the agent code itself is portable Strands/Python. Fallback to ECS/Fargate requires minimal code changes.
