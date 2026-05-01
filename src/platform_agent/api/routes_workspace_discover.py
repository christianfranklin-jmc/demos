"""Workspace-scoped discovery + pills (US2).

Routes:
- POST /workspace/discover — runs scan_metadata against every live
  connection, detects business processes per connection, and merges
  them into a CoverageMatrix (FR-007, FR-010, FR-014).
- POST /workflow/pills — generates ≥6 schema-grounded pill
  suggestions (FR-011, FR-012). For Pinnacle (PG ap/billing/crm/...
  + Snowflake analytical mirror) the six named pills are returned
  verbatim; other workspaces receive schema-driven heuristics.
- POST /workflow/pills/{pill_id}/draft-prd — converts a chosen pill
  into a fully-drafted PRD (FR-013).

All read paths; no LLM call in v1 — pill_generator is deterministic
+ schema-grounded so it works offline. The Strands/Bedrock pill agent
(R5) plugs in here in a follow-up commit; this module owns the
contract surface.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from platform_agent.api.deps import SessionContext, get_session_context
from platform_agent.api.routes_workspace import get_credentials
from platform_agent.drivers import DRIVER_REGISTRY
from platform_agent.tools.pill_generator import generate_pills
from platform_agent.workflow.business_processes import detect_business_processes
from platform_agent.workflow.coverage import build_coverage_matrix
from platform_agent.workflow.discovery_models import (
    BusinessProcess,
    CoverageMatrix,
)
from platform_agent.workflow.pill_models import PillSuggestion, PRDDraft
from platform_agent.workspace.activity_log import write as log_activity
from platform_agent.workspace.activity_models import ActivityKind
from platform_agent.workspace.models import Connection, DriverType
from platform_agent.workspace.registry import get_registry

logger = logging.getLogger(__name__)
router = APIRouter(tags=["workspace-discover"])


# ───── In-memory caches (per process; cleared on restart) ─────

# {connection_id: (BusinessProcess[], metadata, ts)}
_PROCESS_CACHE: dict[str, tuple[list[BusinessProcess], dict[str, Any], datetime]] = {}
# {workspace_id: list[PillSuggestion]}
_PILL_CACHE: dict[str, list[PillSuggestion]] = {}


# ───── Request/response shapes (mirrors contracts/discover.openapi.yaml) ─────


class WorkspaceDiscoverRequest(BaseModel):
    force: bool = Field(
        default=False,
        description="Bypass per-connection discovery cache.",
    )


class PerConnectionDiscoverEnvelope(BaseModel):
    connection_id: str
    processes: list[BusinessProcess]
    kpi_summary: dict[str, int]


class WorkspaceDiscoverResponse(BaseModel):
    coverage_matrix: CoverageMatrix
    per_connection: list[PerConnectionDiscoverEnvelope]
    cross_source_links_found: int


class PillsRequest(BaseModel):
    force: bool = False
    min_pills: int = Field(default=6, ge=3)


class PillsResponse(BaseModel):
    pills: list[PillSuggestion]
    generation_ms: int


# ───── Endpoints ─────


@router.post("/workspace/discover", response_model=WorkspaceDiscoverResponse)
async def workspace_discover(
    payload: WorkspaceDiscoverRequest,
    ctx: Annotated[SessionContext, Depends(get_session_context)],
) -> WorkspaceDiscoverResponse:
    ws = get_registry().get_or_create(ctx.session_id)
    live = ws.live_connections()
    if not live:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "no_live_connections",
                "message": "No live connections in this workspace; add one first.",
            },
        )

    per_connection_results: list[
        tuple[str, list[BusinessProcess], dict[str, Any]]
    ] = []

    for conn in live:
        cached = None if payload.force else _PROCESS_CACHE.get(conn.connection_id)
        if cached is not None:
            processes, metadata, _ts = cached
        else:
            metadata = await asyncio.to_thread(_scan_connection, conn, ctx.session_id)
            processes = detect_business_processes(
                connection_id=conn.connection_id,
                metadata=metadata,
            )
            _PROCESS_CACHE[conn.connection_id] = (processes, metadata, datetime.now(tz=UTC))
            log_activity(
                connection_id=conn.connection_id,
                workspace_id=ctx.session_id,
                kind=ActivityKind.DISCOVERY_COMPLETED,
                payload={
                    "tables": len(metadata.get("tables", [])),
                    "processes": len(processes),
                },
            )
        per_connection_results.append((conn.connection_id, processes, metadata))

    matrix = build_coverage_matrix(
        workspace_id=ctx.session_id,
        per_connection=per_connection_results,
    )
    cross_source_links = sum(
        1 for r in matrix.rows if r.ready_to_combine
    )

    # Pills are workspace-scoped — invalidate when discovery is rerun.
    _PILL_CACHE.pop(str(ctx.session_id), None)

    envelopes = [
        PerConnectionDiscoverEnvelope(
            connection_id=cid,
            processes=processes,
            kpi_summary={
                "tables_scanned": len(metadata.get("tables", [])),
                "columns_profiled": sum(
                    len(t.get("columns", [])) for t in metadata.get("tables", [])
                ),
                "processes_detected": len(processes),
                "elapsed_ms": 0,
            },
        )
        for cid, processes, metadata in per_connection_results
    ]
    return WorkspaceDiscoverResponse(
        coverage_matrix=matrix,
        per_connection=envelopes,
        cross_source_links_found=cross_source_links,
    )


@router.post("/workflow/pills", response_model=PillsResponse)
async def post_pills(
    payload: PillsRequest,
    ctx: Annotated[SessionContext, Depends(get_session_context)],
) -> PillsResponse:
    ws_key = str(ctx.session_id)
    if not payload.force:
        cached_pills = _PILL_CACHE.get(ws_key)
        if cached_pills is not None:
            return PillsResponse(pills=cached_pills, generation_ms=0)

    started = datetime.now(tz=UTC)

    ws = get_registry().get_or_create(ctx.session_id)
    live = ws.live_connections()
    if not live:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "no_live_connections",
                "message": "Add at least one live connection before generating pills.",
            },
        )

    # Pull (or run) per-connection discovery so the pill generator has a
    # schema-grounded view to chew on.
    per_connection: list[tuple[Connection, list[BusinessProcess]]] = []
    for conn in live:
        cached_proc = _PROCESS_CACHE.get(conn.connection_id)
        if cached_proc is None:
            metadata = await asyncio.to_thread(
                _scan_connection, conn, ctx.session_id
            )
            processes = detect_business_processes(
                connection_id=conn.connection_id,
                metadata=metadata,
            )
            _PROCESS_CACHE[conn.connection_id] = (processes, metadata, datetime.now(tz=UTC))
        else:
            processes, _meta, _ts = cached_proc
        per_connection.append((conn, processes))

    pills = generate_pills(
        per_connection=per_connection,
        min_pills=payload.min_pills,
    )
    _PILL_CACHE[ws_key] = pills

    return PillsResponse(
        pills=pills,
        generation_ms=int((datetime.now(tz=UTC) - started).total_seconds() * 1000),
    )


@router.post("/workflow/pills/{pill_id}/draft-prd", response_model=PRDDraft)
async def draft_prd_from_pill(
    pill_id: str,
    ctx: Annotated[SessionContext, Depends(get_session_context)],
) -> PRDDraft:
    ws_key = str(ctx.session_id)
    pills = _PILL_CACHE.get(ws_key) or []
    match = next((p for p in pills if p.pill_id == pill_id), None)
    if match is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    log_activity(
        connection_id=match.source_connection_ids[0],
        workspace_id=ctx.session_id,
        kind=ActivityKind.PILL_CLICKED,
        payload={"pill_id": pill_id, "title": match.title},
    )
    # Stamp the draft with a fresh prd_id so consumers can correlate.
    drafted = match.seed_prd_body.model_copy(update={"prd_id": str(uuid4())})
    return drafted


# ───── Helpers ─────


def _scan_connection(conn: Connection, workspace_id: object) -> dict[str, Any]:
    """Run scan_metadata for a Connection using its cached credentials."""
    import contextlib

    creds = get_credentials(workspace_id, conn.connection_id) or {}
    cls = DRIVER_REGISTRY.get(conn.driver_type.value)
    if cls is None:
        raise ValueError(f"No driver for {conn.driver_type.value!r}")

    kwargs: dict[str, Any] = {**creds}
    if conn.driver_type == DriverType.POSTGRESQL:
        host, _, port = conn.endpoint.partition(":")
        kwargs.setdefault("host", host)
        kwargs.setdefault("port", int(port) if port else 5432)
        kwargs.setdefault("database", conn.scope.split(".")[0])
    elif conn.driver_type == DriverType.ICEBERG:
        kwargs.setdefault("glue_database", conn.scope)
        kwargs.setdefault(
            "warehouse_s3_uri", creds.get("warehouse_s3_uri", "s3://placeholder/warehouse")
        )
        kwargs.setdefault("region", creds.get("region", "us-east-1"))

    driver = cls(**kwargs)
    driver.connect()
    try:
        return driver.scan_metadata()
    finally:
        with contextlib.suppress(Exception):
            driver.close()


# Test/harness hook to clear caches between runs.
def _reset_caches() -> None:
    _PROCESS_CACHE.clear()
    _PILL_CACHE.clear()


__all__ = ["router", "_reset_caches"]
