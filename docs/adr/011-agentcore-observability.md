# ADR-011: AgentCore Observability via OpenTelemetry

**Status**: Accepted

**Date**: 2026-03-26

## Context

The Platform Agent needs observability for production monitoring: trace agent invocations, tool execution timing, Bedrock API calls, and error rates. AgentCore Runtime supports OpenTelemetry-based tracing.

## Options Considered

1. **Custom logging** — `logging.info()` calls in each tool. Simple, but no trace correlation, no distributed tracing, no built-in dashboards.
2. **CloudWatch SDK** — Direct `put_metric_data` and `put_trace_segments` calls. AWS-native but requires manual instrumentation in every function.
3. **OpenTelemetry auto-instrumentation** — `strands-agents[otel]` + AWS OpenTelemetry distro. Zero-code instrumentation for Bedrock API calls, HTTP requests, and tool spans. CloudWatch as the default sink when running on AgentCore Runtime.

## Decision

Use **OpenTelemetry auto-instrumentation** via the `opentelemetry-instrument` command as the Docker entrypoint. The AWS OpenTelemetry distro routes traces to CloudWatch automatically when running on AgentCore Runtime.

The Dockerfile CMD is:
```
opentelemetry-instrument python -m agent
```

Environment variables:
- `AGENT_OBSERVABILITY_ENABLED=true`
- `OTEL_PYTHON_DISTRO=aws_distro`
- `OTEL_PYTHON_CONFIGURATOR=aws_configurator`

## Consequences

**Positive:**
- Zero-code instrumentation — Bedrock API calls, tool executions, and HTTP requests are traced automatically
- CloudWatch Traces as the default sink — no additional infrastructure
- `strands-agents[otel]` adds Strands-specific spans (tool name, duration, input/output)
- Custom spans can be added optionally for business-level metrics

**Negative:**
- Auto-instrumentation adds ~50ms startup overhead
- Trace volume can be significant (each tool call generates multiple spans)
- CloudWatch Traces pricing applies ($0.50 per million spans ingested)
- Custom span attributes require manual code if auto-instrumentation doesn't capture needed dimensions
