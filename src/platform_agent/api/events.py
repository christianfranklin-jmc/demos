"""Pydantic v2 models for the SSE event schema v1.

Canonical shapes for every event emitted over `POST /workflow/step`. The
frontend's agentcore-client/parsers/v1/ must stay in lockstep with this file.
Contract tests (tests/contract/test_sse_events.py) enforce round-trip equality.

See contracts/sse-events.md for wire-level rules and ADR-015 D14 for rationale.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


class _EventBase(BaseModel):
    """Shared event base. Every event carries a schema version `v` and a timestamp."""

    model_config = ConfigDict(extra="forbid")

    v: Literal[1] = 1
    t: datetime = Field(default_factory=_now)


class HeartbeatEvent(_EventBase):
    """Passive 10s idle heartbeat. Frontend resets its silence timer on each one."""

    # event-name channel: "heartbeat"


class ToolStartEvent(_EventBase):
    """Emitted when a @tool function begins executing."""

    run_id: UUID
    tool: str
    args_summary: Annotated[str, Field(max_length=200)]


class ToolProgressEvent(_EventBase):
    """Emitted at natural progress boundaries inside a long-running tool."""

    run_id: UUID
    tool: str
    index: int | None = None
    total: int | None = None
    note: Annotated[str, Field(max_length=100)]


class ToolResultEvent(_EventBase):
    """Emitted when a @tool function returns. `summary` is LLM-free."""

    run_id: UUID
    tool: str
    summary: Annotated[str, Field(max_length=500)]


class MessageEvent(_EventBase):
    """Streaming chat output from Bedrock. `delta=True` = append; False = replace."""

    run_id: UUID
    role: Literal["assistant"] = "assistant"
    content: str
    delta: bool = True


# Artifact payloads — structural; see data-model.md §4 for definitions.


class PrdSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    heading: str
    body: str
    cited_tables: list[str]
    completeness_contribution: Annotated[float, Field(ge=0.0, le=1.0)]


class PrdPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sections: list[PrdSection]
    completeness: Annotated[float, Field(ge=0.0, le=1.0)]


class Entity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    label: str
    source_table: str
    row_count_est: int | None = None
    key_columns: list[str] = Field(default_factory=list)


class Relationship(BaseModel):
    model_config = ConfigDict(extra="forbid")

    from_entity_id: str
    to_entity_id: str
    from_column: str
    to_column: str
    cardinality: Literal["1:1", "1:N", "N:1", "N:M"]
    inferred: bool = False


class ConceptualModelPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entities: list[Entity]
    relationships: list[Relationship]


class LogicalField(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    data_type: str
    nullable: bool
    sample_values: Annotated[list[str], Field(max_length=5)] = Field(default_factory=list)
    is_measure: bool = False
    role: Literal["id", "dimension", "measure", "attribute"]


class LogicalTable(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    label: str
    grain: str | None = None
    fields: list[LogicalField]


class LogicalModelPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tables: list[LogicalTable]


ArtifactPayload = PrdPayload | ConceptualModelPayload | LogicalModelPayload


class ArtifactUpdateEvent(_EventBase):
    """Incremental artifact render — replaces any prior update with the same (step, artifact_type)."""

    run_id: UUID
    step: Literal["requirements", "conceptual", "logical", "detailed"]
    artifact_type: Literal["prd", "conceptual_model", "logical_model"]
    payload: ArtifactPayload


class ArtifactReadyEvent(_EventBase):
    """Terminal event for Step 4 only — tells the frontend to fetch the zip."""

    run_id: UUID
    step: Literal["detailed"] = "detailed"
    handle: UUID
    size_bytes: Annotated[int, Field(gt=0)]
    file_count: Annotated[int, Field(gt=0)]
    expires_in_s: Annotated[int, Field(gt=0)]
    download_url: str


ErrorCode = Literal[
    "tool_error",
    "agent_error",
    "cancelled",
    "timeout",
    "unauthorized",
    "validation_error",
    "memory_unreachable",
]


class ErrorEvent(_EventBase):
    """Terminal error. If `retriable` the frontend may offer a retry; never for unauthorized/validation."""

    run_id: UUID | None = None
    code: ErrorCode
    message: str
    retriable: bool


class DoneEvent(_EventBase):
    """Terminal success for non-Step-4 steps."""

    run_id: UUID
    step: Literal["requirements", "conceptual", "logical"]


SSEEvent = (
    HeartbeatEvent
    | ToolStartEvent
    | ToolProgressEvent
    | ToolResultEvent
    | MessageEvent
    | ArtifactUpdateEvent
    | ArtifactReadyEvent
    | ErrorEvent
    | DoneEvent
)


EVENT_NAMES: dict[type[_EventBase], str] = {
    HeartbeatEvent: "heartbeat",
    ToolStartEvent: "tool_start",
    ToolProgressEvent: "tool_progress",
    ToolResultEvent: "tool_result",
    MessageEvent: "message",
    ArtifactUpdateEvent: "artifact_update",
    ArtifactReadyEvent: "artifact_ready",
    ErrorEvent: "error",
    DoneEvent: "done",
}


TERMINAL_EVENT_TYPES: frozenset[type[_EventBase]] = frozenset(
    {ArtifactReadyEvent, ErrorEvent, DoneEvent}
)


def event_name(event: _EventBase) -> str:
    """Return the SSE event channel name for a given Pydantic event instance."""
    return EVENT_NAMES[type(event)]


def is_terminal(event: _EventBase) -> bool:
    """True if the event closes the SSE stream."""
    return type(event) in TERMINAL_EVENT_TYPES
