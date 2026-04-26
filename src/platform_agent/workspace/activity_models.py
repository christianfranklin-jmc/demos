"""ActivityLogEntry — append-only audit row (data-model.md §16).

Owned by the connection that "owns" the action: e.g., `connection_added`
lands in that connection's log; `redundancy_decision` lands in the
target Iceberg connection's log; `ttyd_query` lands in the connection
the planner ultimately queried.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class ActivityKind(StrEnum):
    CONNECTION_ADDED = "connection_added"
    CONNECTION_ERROR = "connection_error"
    CONNECTION_RETRIED = "connection_retried"
    DISCOVERY_COMPLETED = "discovery_completed"
    PILL_CLICKED = "pill_clicked"
    PRD_DRAFTED = "prd_drafted"
    REDUNDANCY_DECISION = "redundancy_decision"
    PROVISIONING_STARTED = "provisioning_started"
    AGENT_STATE_CHANGE = "agent_state_change"
    VALIDATION_RESULT = "validation_result"
    PRODUCT_REGISTERED = "product_registered"
    PRODUCT_PROMOTED = "product_promoted"
    TTYD_QUERY = "ttyd_query"


class ActivityLogEntry(BaseModel):
    entry_id: str
    connection_id: str
    workspace_id: UUID
    kind: ActivityKind
    payload: dict[str, Any] = Field(default_factory=dict)
    ts: datetime
