"""Discovery + coverage Pydantic models (data-model.md §8, §9).

Per-connection BusinessProcess detection + workspace-level CoverageMatrix
that drives Step 1's coverage map and the pill agent's input.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from platform_agent.semantic.models import Domain


class VolumeSignal(BaseModel):
    row_count: int = 0
    dollar_total: Decimal | None = None
    currency: str | None = None


class BusinessProcess(BaseModel):
    process_id: str
    connection_id: str
    name: str
    domain: Domain = Domain.UNSPECIFIED
    volume_signal: VolumeSignal = Field(default_factory=VolumeSignal)
    last_activity_ts: datetime | None = None
    sparkline: list[float] = Field(default_factory=list)
    backing_tables: list[str] = Field(default_factory=list)


class ProcessPresence(BaseModel):
    present: bool
    backing_tables: list[str] = Field(default_factory=list)


class CoverageRow(BaseModel):
    process_name: str
    per_connection: dict[str, ProcessPresence] = Field(default_factory=dict)
    shared_keys: list[str] = Field(default_factory=list)
    ready_to_combine: bool = False


class CoverageMatrix(BaseModel):
    matrix_id: str
    workspace_id: UUID
    rows: list[CoverageRow] = Field(default_factory=list)
