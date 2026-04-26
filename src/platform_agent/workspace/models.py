"""Workspace + Connection Pydantic v2 models (data-model.md §1, §2).

A Workspace is per-tab/session (Q1) and lives in-memory only. Each
Connection contributes a `DatabaseDriver` instance to the workspace's
`MultiSourceDriver` and owns a per-connection durable store keyed by
`connection_id`.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class DriverType(StrEnum):
    POSTGRESQL = "postgresql"
    REDSHIFT = "redshift"
    SNOWFLAKE = "snowflake"
    DATABRICKS = "databricks"
    ICEBERG = "iceberg"


class ConnectionStatus(StrEnum):
    CONNECTING = "connecting"
    SCANNING = "scanning"
    LIVE = "live"
    ERROR = "error"


class ConnectionError(BaseModel):
    code: str
    message: str
    retryable: bool = True


class ConnectionKPIs(BaseModel):
    tables_total: int = 0
    rows_estimated: int = 0
    processes_detected: int = 0


class Connection(BaseModel):
    """Durable identity + ephemeral state for one source binding."""

    connection_id: str = Field(..., description="SHA-256 of (driver, endpoint, scope).")
    driver_type: DriverType
    display_name: str = Field(..., min_length=1, max_length=80)
    endpoint: str
    scope: str
    credential_ref: str | None = None
    status: ConnectionStatus = ConnectionStatus.CONNECTING
    error: ConnectionError | None = None
    kpis: ConnectionKPIs = Field(default_factory=ConnectionKPIs)
    added_at: datetime
    last_synced_at: datetime | None = None
    tags: list[str] = Field(default_factory=list)

    @field_validator("display_name")
    @classmethod
    def _strip_display_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("display_name cannot be blank")
        return v


class Lens(BaseModel):
    """Active TTYD/discovery lens. `kind=all` covers every live connection."""

    kind: str = Field(..., pattern=r"^(all|connection)$")
    connection_id: str | None = None

    @field_validator("connection_id")
    @classmethod
    def _connection_id_required_for_per_source(
        cls, v: str | None, info: Any
    ) -> str | None:
        if info.data.get("kind") == "connection" and not v:
            raise ValueError("connection_id required when kind=connection")
        if info.data.get("kind") == "all" and v:
            raise ValueError("connection_id must be empty when kind=all")
        return v


class Workspace(BaseModel):
    """Per-tab in-memory record. Same UUID as the existing session id."""

    workspace_id: UUID
    created_at: datetime
    connections: list[Connection] = Field(default_factory=list)
    active_lens: Lens = Field(default_factory=lambda: Lens(kind="all"))

    def live_connections(self) -> list[Connection]:
        return [c for c in self.connections if c.status == ConnectionStatus.LIVE]

    def find(self, connection_id: str) -> Connection | None:
        return next((c for c in self.connections if c.connection_id == connection_id), None)
