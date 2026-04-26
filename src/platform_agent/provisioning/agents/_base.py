"""Provisioning agent contract (US3).

Every agent in the 7-agent DAG implements `run(ctx) -> AgentOutput`. The
orchestrator drives the lifecycle (state transitions, retry, event
emission); agents focus on the work + artifacts they produce.

v1 agents are stubs that simulate realistic-looking artifacts (column
lists, dbt model paths, Iceberg table names) without actually running
dbt or writing to S3. The orchestrator + event-stream architecture is
the load-bearing piece; agent internals can be filled in incrementally
(e.g., promoting `patterns/migration-agent/extract_schema.py` into
`schema_agent.run()`).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from platform_agent.provisioning.models import AgentId, Artifact
from platform_agent.workflow.pill_models import PRDDraft


@dataclass
class AgentContext:
    """What every agent receives. Passed by reference; agents mutate via outputs."""

    run_id: str
    workspace_id: str
    target_connection_id: str
    prd: PRDDraft
    upstream_artifacts: dict[AgentId, list[Artifact]] = field(default_factory=dict)
    # Bound by the orchestrator — emit progress messages observable on SSE.
    emit_progress: Callable[[str], None] = field(default=lambda _: None)
    # Bound by the orchestrator — emit named artifacts as they're produced.
    emit_artifact: Callable[[Artifact], None] = field(default=lambda _: None)


@dataclass
class AgentOutput:
    """Everything an agent reports back. Failure → set `error`."""

    artifacts: list[Artifact] = field(default_factory=list)
    error: dict[str, Any] | None = None  # {code, message, retryable}
    latency_ms_p95: int | None = None


# Agent runner signature.
AgentRunner = Callable[[AgentContext], AgentOutput]
