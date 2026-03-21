# ADR-002: LLM Provider

**Status**: Accepted

**Date**: 2026-03-20

## Context

The agent requires a large language model for reasoning, tool use, and code generation. The model must support function calling (tool use), long context windows for ingesting database schemas, and high-quality code generation for dbt SQL and YAML. The solution must operate within AWS for enterprise governance and data residency requirements.

## Options Considered

1. **Amazon Bedrock with Anthropic Claude models** — Claude Sonnet 4 for standard tasks, Claude Opus 4 for complex reasoning. Accessed via Bedrock Converse API. Data stays within AWS. IAM-based access control.
2. **Anthropic API direct** — Same Claude models but requires data to leave the AWS VPC for API calls. Separate API key management outside AWS IAM.
3. **Amazon Bedrock with Amazon Nova models** — Lower cost but weaker on complex code generation and multi-step reasoning compared to Claude.
4. **OpenAI via Bedrock or direct** — GPT-4o available on Bedrock but Strands SDK has strongest integration with Bedrock-native Claude models.

## Decision

Use **Amazon Bedrock** as the LLM provider with **Claude Sonnet 4** as the default model and **Claude Opus 4** available for complex reasoning tasks (dimensional model design, semantic layer authoring).

## Consequences

- **Positive**: Data never leaves AWS. IAM integration for access control. No separate API keys to manage.
- **Positive**: Strands Agents SDK has native `BedrockModel` class with streaming, tool use, and interleaved thinking support.
- **Positive**: Claude Sonnet 4 offers strong cost/quality balance for most tasks; Opus 4 provides a ceiling for difficult tasks.
- **Negative**: Bedrock model availability varies by region; must verify Claude model access in target region.
- **Negative**: Bedrock throttling limits may require quota increases for production workloads.
