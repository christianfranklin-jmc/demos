"""Workspace + Connection routes (002-dsa-hub-pinnacle US1).

Implements `contracts/workspace.openapi.yaml`:
- GET    /workspace/connections           — list
- POST   /workspace/connection            — add
- DELETE /workspace/connection/{id}       — remove
- POST   /workspace/connection/{id}/retry — retry an errored connection
- GET    /workspace/kpis                  — workspace-wide KPI strip

Connection identity is derived deterministically from
`(driver_type, endpoint, scope)` so the same source produces the same
`connection_id` across tabs/sessions (research.md R2). Server-side
state is per-tab in-memory only (Q1) — durable per-connection assets
are written through the connection's own ConnectionStore.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from platform_agent.api.deps import SessionContext, get_session_context
from platform_agent.workspace.activity_log import write as log_activity
from platform_agent.workspace.activity_models import ActivityKind
from platform_agent.workspace.connection_id import derive_connection_id
from platform_agent.workspace.lifecycle import schedule_connection_lifecycle
from platform_agent.workspace.models import (
    Connection,
    ConnectionKPIs,
    ConnectionStatus,
    DriverType,
)
from platform_agent.workspace.registry import get_registry

logger = logging.getLogger(__name__)

router = APIRouter(tags=["workspace"])


# ───── Request/response shapes ─────


class AddConnectionRequest(BaseModel):
    driver_type: DriverType
    display_name: str = Field(..., min_length=1, max_length=80)
    endpoint: str
    scope: str
    credentials: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)


class ListConnectionsResponse(BaseModel):
    connections: list[Connection]


class WorkspaceKPIs(BaseModel):
    sources_connected: int
    tables_total: int
    rows_total: int
    processes_detected: int
    semantic_entities_total: int
    last_updated: datetime


# ───── Endpoints ─────


@router.get("/workspace/connections", response_model=ListConnectionsResponse)
async def list_connections(
    ctx: Annotated[SessionContext, Depends(get_session_context)],
) -> ListConnectionsResponse:
    ws = get_registry().get_or_create(ctx.session_id)
    return ListConnectionsResponse(connections=list(ws.connections))


@router.post(
    "/workspace/connection",
    response_model=Connection,
    status_code=status.HTTP_201_CREATED,
)
async def add_connection(
    payload: AddConnectionRequest,
    ctx: Annotated[SessionContext, Depends(get_session_context)],
) -> Connection:
    connection_id = derive_connection_id(
        payload.driver_type.value, payload.endpoint, payload.scope
    )

    registry = get_registry()
    ws = registry.get_or_create(ctx.session_id)

    if ws.find(connection_id) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "duplicate_connection",
                "message": "A connection with this (driver_type, endpoint, scope) already exists.",
                "connection_id": connection_id,
            },
        )

    # Credentials never persist server-side: held only in the per-tab session
    # cache below, keyed by the same UUID that scopes the workspace.
    credential_ref = _stash_credentials(ctx.session_id, connection_id, payload.credentials)

    connection = Connection(
        connection_id=connection_id,
        driver_type=payload.driver_type,
        display_name=payload.display_name,
        endpoint=payload.endpoint,
        scope=payload.scope,
        credential_ref=credential_ref,
        status=ConnectionStatus.CONNECTING,
        kpis=ConnectionKPIs(),
        added_at=datetime.now(tz=UTC),
        tags=list(payload.tags),
    )
    registry.add_connection(ctx.session_id, connection)

    log_activity(
        connection_id=connection_id,
        workspace_id=ctx.session_id,
        kind=ActivityKind.CONNECTION_ADDED,
        payload={
            "driver_type": connection.driver_type.value,
            "scope": connection.scope,
            "display_name": connection.display_name,
        },
    )

    # Kick off the async lifecycle worker (connecting → scanning → live).
    schedule_connection_lifecycle(workspace_id=ctx.session_id, connection_id=connection_id)
    return connection


# ───── Demo presets — local-mode only ─────
#
# Reads connection metadata + credentials from os.environ (i.e. .env)
# server-side and adds the connection in one click. Credentials stay
# in the per-tab session cache exactly like /workspace/connection;
# they never appear in the client bundle or HTTP response.

_PRESETS: dict[str, dict[str, Any]] = {
    "pinnacle_pg": {
        "driver_type": "postgresql",
        "display_name": "Pinnacle PG",
        "scope_template": "{db}.public",
        # Required env vars for this preset.
        "env_required": ["DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD"],
        "env_optional": {"DB_SSLMODE": "require"},
    },
    "pinnacle_sf": {
        "driver_type": "snowflake",
        "display_name": "Pinnacle SF",
        "scope_template": "{db}.{schema}",
        "env_required": ["SF_ACCOUNT", "SF_DATABASE"],
        "env_optional": {
            "SF_USER": "",
            "SF_PASSWORD": "",
            "SF_AUTHENTICATOR": "externalbrowser",
            "SF_ROLE": "",
            "SF_WAREHOUSE": "COMPUTE_WH",
            "SF_SCHEMA": "ANALYTICS",
        },
    },
}


class PresetSummary(BaseModel):
    name: str
    label: str
    driver_type: str
    available: bool
    missing_env: list[str] = Field(default_factory=list)


class PresetListResponse(BaseModel):
    presets: list[PresetSummary]


def _build_preset_payload(name: str) -> AddConnectionRequest | None:
    import os

    spec = _PRESETS.get(name)
    if spec is None:
        return None
    missing = [k for k in spec["env_required"] if not os.environ.get(k)]
    if missing:
        return None

    if name == "pinnacle_pg":
        host = os.environ["DB_HOST"]
        port = int(os.environ.get("DB_PORT", "5432"))
        db = os.environ["DB_NAME"]
        return AddConnectionRequest(
            driver_type=DriverType.POSTGRESQL,
            display_name=spec["display_name"],
            endpoint=f"{host}:{port}",
            scope=spec["scope_template"].format(db=db),
            credentials={
                "host": host,
                "port": port,
                "database": db,
                "user": os.environ["DB_USER"],
                "password": os.environ["DB_PASSWORD"],
                "sslmode": os.environ.get("DB_SSLMODE", "require"),
            },
            tags=["pinnacle", "preset"],
        )
    if name == "pinnacle_sf":
        account = os.environ["SF_ACCOUNT"]
        db = os.environ["SF_DATABASE"]
        schema = os.environ.get("SF_SCHEMA", "ANALYTICS")
        return AddConnectionRequest(
            driver_type=DriverType.SNOWFLAKE,
            display_name=spec["display_name"],
            endpoint=account,
            scope=spec["scope_template"].format(db=db, schema=schema),
            credentials={
                "account": account,
                "user": os.environ.get("SF_USER", ""),
                "password": os.environ.get("SF_PASSWORD", ""),
                "authenticator": os.environ.get("SF_AUTHENTICATOR", "externalbrowser"),
                "role": os.environ.get("SF_ROLE", ""),
                "warehouse": os.environ.get("SF_WAREHOUSE", "COMPUTE_WH"),
                "database": db,
                "schema": schema,
            },
            tags=["pinnacle", "preset"],
        )
    return None


@router.get("/workspace/connection-presets", response_model=PresetListResponse)
async def list_presets(
    ctx: Annotated[SessionContext, Depends(get_session_context)],  # noqa: ARG001
) -> PresetListResponse:
    """List demo presets + which ones are wired up via .env."""
    import os

    out: list[PresetSummary] = []
    for name, spec in _PRESETS.items():
        missing = [k for k in spec["env_required"] if not os.environ.get(k)]
        out.append(
            PresetSummary(
                name=name,
                label=spec["display_name"],
                driver_type=spec["driver_type"],
                available=not missing,
                missing_env=missing,
            )
        )
    return PresetListResponse(presets=out)


@router.post(
    "/workspace/connection-presets/{name}",
    response_model=Connection,
    status_code=status.HTTP_201_CREATED,
)
async def use_preset(
    name: str,
    ctx: Annotated[SessionContext, Depends(get_session_context)],
) -> Connection:
    """One-click add a connection from server-side .env vars."""
    payload = _build_preset_payload(name)
    if payload is None:
        spec = _PRESETS.get(name)
        if spec is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "unknown_preset", "message": f"no preset {name!r}"},
            )
        import os

        missing = [k for k in spec["env_required"] if not os.environ.get(k)]
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "preset_unavailable",
                "message": f"preset {name!r} requires env vars: {missing}",
                "missing_env": missing,
            },
        )
    # Reuse the same code path as the manual add — keeps deduping,
    # activity-log, lifecycle scheduling all uniform.
    return await add_connection(payload, ctx)


@router.delete(
    "/workspace/connection/{connection_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_connection(
    connection_id: str,
    ctx: Annotated[SessionContext, Depends(get_session_context)],
) -> None:
    removed = get_registry().remove_connection(ctx.session_id, connection_id)
    if not removed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    _drop_credentials(ctx.session_id, connection_id)


@router.post("/workspace/connection/{connection_id}/retry", response_model=Connection)
async def retry_connection(
    connection_id: str,
    ctx: Annotated[SessionContext, Depends(get_session_context)],
) -> Connection:
    registry = get_registry()
    ws = registry.get(ctx.session_id)
    if ws is None or ws.find(connection_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    updated = registry.update_connection(
        ctx.session_id,
        connection_id,
        status=ConnectionStatus.CONNECTING,
        error=None,
    )
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    log_activity(
        connection_id=connection_id,
        workspace_id=ctx.session_id,
        kind=ActivityKind.CONNECTION_RETRIED,
        payload={"display_name": updated.display_name},
    )
    schedule_connection_lifecycle(workspace_id=ctx.session_id, connection_id=connection_id)
    return updated


@router.get("/workspace/kpis", response_model=WorkspaceKPIs)
async def workspace_kpis(
    ctx: Annotated[SessionContext, Depends(get_session_context)],
) -> WorkspaceKPIs:
    ws = get_registry().get_or_create(ctx.session_id)
    live = ws.live_connections()
    return WorkspaceKPIs(
        sources_connected=len(live),
        tables_total=sum(c.kpis.tables_total for c in live),
        rows_total=sum(c.kpis.rows_estimated for c in live),
        processes_detected=sum(c.kpis.processes_detected for c in live),
        # Semantic entity totals require reading per-connection stores;
        # left at 0 here and surfaced for real once US5 lands.
        semantic_entities_total=0,
        last_updated=datetime.now(tz=UTC),
    )


# ───── Per-tab credential cache (process-local, ephemeral) ─────

# Holds raw credentials for the lifetime of the backend process. Keyed by
# (session_uuid, connection_id) so a tab's credentials never leak into
# another tab's workspace. Discarded when the connection is removed.
_creds: dict[tuple[str, str], dict[str, Any]] = {}
_creds_lock = asyncio.Lock()


def _stash_credentials(
    session_id: object, connection_id: str, credentials: dict[str, Any]
) -> str | None:
    if not credentials:
        return None
    key = (str(session_id), connection_id)
    _creds[key] = dict(credentials)
    return f"session:{key[0]}:{connection_id}"


def _drop_credentials(session_id: object, connection_id: str) -> None:
    _creds.pop((str(session_id), connection_id), None)


def get_credentials(session_id: object, connection_id: str) -> dict[str, Any] | None:
    """Look up a stashed credential payload (used by the lifecycle worker)."""
    return _creds.get((str(session_id), connection_id))


__all__ = ["router", "get_credentials"]
