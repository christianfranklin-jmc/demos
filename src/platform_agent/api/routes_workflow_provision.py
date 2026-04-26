"""Provisioning routes (T079 + T080, US3).

POST /workflow/provision           — accept a PRD; queue a run; 201
GET  /workflow/provision/{run_id}  — snapshot of run state
GET  /workflow/provision/{run_id}/events  — SSE schema v2 stream
POST /workflow/provision/{run_id}/retry   — reset failed agent + downstream

Acceptance is gated on the workspace having a live Iceberg/Glue
connection (FR-031, Q3). The redundancy-cleared check (FR-026) is a
soft pass-through here in v1 — the caller signals it via
`redundancy_cleared=True` on the request body. Phase 8 wires the real
check via `routes_redundancy.RedundancyReport.cleared_to_provision`.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from platform_agent.api.deps import SessionContext, get_session_context
from platform_agent.provisioning import orchestrator
from platform_agent.provisioning.models import AgentId, ProvisioningRun
from platform_agent.workflow.pill_models import PRDDraft
from platform_agent.workspace.models import ConnectionStatus, DriverType
from platform_agent.workspace.read_only import ReadOnlyViolation, assert_read_only
from platform_agent.workspace.registry import get_registry

logger = logging.getLogger(__name__)
router = APIRouter(tags=["provisioning"])


class ProvisionRequest(BaseModel):
    prd: PRDDraft
    redundancy_report_id: str | None = None
    # v1 soft gate; Phase 8 replaces this with a real RedundancyReport lookup.
    redundancy_cleared: bool = Field(
        default=True,
        description="Caller asserts the redundancy gate cleared. Phase 8 enforces.",
    )


class RetryRequest(BaseModel):
    agent_id: AgentId


@router.post(
    "/workflow/provision",
    response_model=ProvisioningRun,
    status_code=status.HTTP_201_CREATED,
)
async def post_provision(
    payload: ProvisionRequest,
    ctx: Annotated[SessionContext, Depends(get_session_context)],
) -> ProvisioningRun:
    # Read-only enforcement on every source pull SQL (defence in depth — the
    # PRDDraft already validates these, but a re-validation here gates
    # against any caller that constructs a payload outside the model layer).
    for pull in payload.prd.source_pulls:
        try:
            assert_read_only(pull.sql)
        except ReadOnlyViolation as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "read_only_violation", "message": str(exc)},
            ) from exc

    # Phase 8 hardens the gate: when a `redundancy_report_id` is supplied
    # we look it up; the soft `redundancy_cleared` flag remains the v1
    # default for callers (e.g., the auto-flow from a fresh pill click)
    # that haven't run the gate yet — those will be unable to opt out
    # once the gate is mandatory in a follow-up.
    if payload.redundancy_report_id:
        from platform_agent.api.routes_redundancy import get_report

        report = get_report(payload.redundancy_report_id)
        if report is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "redundancy_report_unknown",
                    "message": (
                        f"redundancy_report_id={payload.redundancy_report_id} "
                        "not found"
                    ),
                },
            )
        if not report.cleared_to_provision:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "redundancy_not_cleared",
                    "message": (
                        "Redundancy report has not cleared this PRD; record "
                        "decisions via /workflow/redundancy-check/{id}/decide "
                        "first."
                    ),
                },
            )
    elif not payload.redundancy_cleared:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "redundancy_not_cleared",
                "message": "Redundancy gate has not cleared this PRD for provisioning.",
            },
        )

    # FR-031, Q3: workspace MUST have ≥1 live iceberg-driver connection.
    ws = get_registry().get_or_create(ctx.session_id)
    iceberg_connections = [
        c
        for c in ws.connections
        if c.driver_type == DriverType.ICEBERG and c.status == ConnectionStatus.LIVE
    ]
    if not iceberg_connections:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "no_iceberg_target",
                "message": "Add an Iceberg/Glue connection to the workspace before provisioning.",
            },
        )

    # If the PRD's target.connection_id is the sentinel from the pill
    # generator, swap it for the first live iceberg connection.
    if payload.prd.target.connection_id == "ICEBERG_TARGET_REQUIRED":
        payload.prd.target.connection_id = iceberg_connections[0].connection_id
    elif not any(
        c.connection_id == payload.prd.target.connection_id for c in iceberg_connections
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "no_iceberg_target",
                "message": (
                    "PRD target.connection_id does not resolve "
                    "to a live Iceberg connection."
                ),
            },
        )

    run = orchestrator.queue_run(workspace_id=str(ctx.session_id), prd=payload.prd)
    # Fire and forget: the run advances asynchronously; clients subscribe
    # via /events.
    asyncio.create_task(orchestrator.execute_run(run.run_id))
    return run


@router.get(
    "/workflow/provision/{run_id}",
    response_model=ProvisioningRun,
)
async def get_provision_snapshot(
    run_id: str,
    ctx: Annotated[SessionContext, Depends(get_session_context)],  # noqa: ARG001
) -> ProvisioningRun:
    run = orchestrator.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return run


@router.post("/workflow/provision/{run_id}/retry")
async def post_retry(
    run_id: str,
    payload: RetryRequest,
    ctx: Annotated[SessionContext, Depends(get_session_context)],  # noqa: ARG001
) -> dict[str, Any]:
    if not orchestrator.reset_for_retry(run_id, payload.agent_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    asyncio.create_task(orchestrator.execute_run(run_id))
    return {"status": "queued", "run_id": run_id, "from_agent": payload.agent_id.value}


@router.get("/workflow/provision/{run_id}/events")
async def get_provision_events(
    run_id: str,
    ctx: Annotated[SessionContext, Depends(get_session_context)],  # noqa: ARG001
) -> StreamingResponse:
    queue = orchestrator.subscribe(run_id)
    if queue is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    async def event_stream() -> AsyncIterator[bytes]:
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=10.0)
                except TimeoutError:
                    # Emit a passive heartbeat so the v2 parser can reset
                    # its silence timer (matches the v1 SSEEmitter pattern).
                    yield b"event: heartbeat\ndata: {}\n\n"
                    continue
                if event is None:
                    break  # orchestrator finished
                payload = event.model_dump(mode="json")
                kind = event.kind
                yield f"event: {kind}\ndata: {json.dumps(payload)}\n\n".encode()
        finally:
            orchestrator.unsubscribe(run_id, queue)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


__all__ = ["router"]
