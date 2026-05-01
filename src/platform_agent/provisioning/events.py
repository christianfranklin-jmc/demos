"""SSE event schema v2 — provisioning DAG (US3, R6).

Additive over the v1 schema in `api/events.py`. Every v2 event carries
``v: 2`` so the frontend parser at
``frontend/src/lib/agentcore-client/parsers/v2/`` can route on the
envelope. Eleven event kinds cover the 7-agent orchestration DAG:

  agent.started / agent.progress / agent.completed / agent.failed
  kpi.tick / artifact.produced
  validation.started / validation.result
  run.completed / run.needs_replan
  heartbeat
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from platform_agent.provisioning.models import AgentId, KpiTick


def _now() -> datetime:
    return datetime.now(tz=UTC)


class _V2Envelope(BaseModel):
    """Common envelope on every v2 event."""

    model_config = ConfigDict(extra="forbid")

    v: Literal[2] = 2
    run_id: str
    seq: int = Field(ge=0)
    ts: datetime = Field(default_factory=_now)


class AgentStartedEvent(_V2Envelope):
    kind: Literal["agent.started"] = "agent.started"
    agent_id: AgentId
    attempt: int = 1


class AgentProgressEvent(_V2Envelope):
    kind: Literal["agent.progress"] = "agent.progress"
    agent_id: AgentId
    message: str


class ArtifactProducedEvent(_V2Envelope):
    kind: Literal["artifact.produced"] = "artifact.produced"
    agent_id: AgentId
    artifact: dict[str, Any]


class AgentCompletedEvent(_V2Envelope):
    kind: Literal["agent.completed"] = "agent.completed"
    agent_id: AgentId
    artifacts: list[dict[str, Any]] = Field(default_factory=list)
    latency_ms_p95: int | None = None


class AgentFailedEvent(_V2Envelope):
    kind: Literal["agent.failed"] = "agent.failed"
    agent_id: AgentId
    error_code: str
    error_message: str
    retryable: bool = True


class KpiTickEvent(_V2Envelope):
    kind: Literal["kpi.tick"] = "kpi.tick"
    tick: KpiTick


class ValidationStartedEvent(_V2Envelope):
    kind: Literal["validation.started"] = "validation.started"
    question_count: int


class ValidationResultEvent(_V2Envelope):
    kind: Literal["validation.result"] = "validation.result"
    question: str
    state: Literal["passed", "failed"]
    sql_executed: str | None = None
    latency_ms: int | None = None
    judge_reasoning: str = ""


class RunCompletedEvent(_V2Envelope):
    kind: Literal["run.completed"] = "run.completed"
    product_id: str
    product_state: Literal["final", "provisional"]
    validation_pass_rate: float


class RunNeedsReplanEvent(_V2Envelope):
    kind: Literal["run.needs_replan"] = "run.needs_replan"
    reason: str
    suggested_agent: AgentId | None = None


class V2HeartbeatEvent(_V2Envelope):
    kind: Literal["heartbeat"] = "heartbeat"


# Discriminated union for typed dispatch on the producer side.
ProvisionEvent = (
    AgentStartedEvent
    | AgentProgressEvent
    | AgentCompletedEvent
    | AgentFailedEvent
    | KpiTickEvent
    | ArtifactProducedEvent
    | ValidationStartedEvent
    | ValidationResultEvent
    | RunCompletedEvent
    | RunNeedsReplanEvent
    | V2HeartbeatEvent
)


def event_kind(event: ProvisionEvent) -> str:
    """SSE channel name for the given event."""
    return event.kind


__all__ = [
    "ProvisionEvent",
    "AgentStartedEvent",
    "AgentProgressEvent",
    "AgentCompletedEvent",
    "AgentFailedEvent",
    "KpiTickEvent",
    "ArtifactProducedEvent",
    "ValidationStartedEvent",
    "ValidationResultEvent",
    "RunCompletedEvent",
    "RunNeedsReplanEvent",
    "V2HeartbeatEvent",
    "event_kind",
]
