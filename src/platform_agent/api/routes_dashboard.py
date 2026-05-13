"""POST /workflow/dashboard — reverse-engineer a BI dashboard screenshot into dbt models.

Accepts a dashboard screenshot (as a base64 data URL), scans the connected source
schema, calls Bedrock vision to extract metrics, maps them to source tables, and
delivers a dbt project zip via the standard SSE + artifact_ready flow.
"""
from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextvars import copy_context
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from .deps import SessionContext, get_session_context
from .events import ErrorEvent
from .routes_workflow import SourceConnection
from .sse import SSEEmitter, heartbeat_emitter, make_progress_emitter
from .zip_stream import ArtifactStore

logger = logging.getLogger(__name__)
router = APIRouter()


class DashboardRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    image_data: str = Field(description="Base64 data URL: 'data:image/png;base64,...'")
    connection: SourceConnection
    user_message: str = "Analyze this dashboard"
    sigma_workbook_name: str | None = None
    sigma_sql: str | None = None


@router.post("/workflow/dashboard")
async def post_dashboard(
    request: Request,
    body: DashboardRequest,
    session: SessionContext = Depends(get_session_context),
) -> StreamingResponse:
    """Analyze a dashboard screenshot and generate a dbt project. Returns an SSE stream."""
    if not body.image_data.startswith("data:image/"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": {
                    "code": "validation_error",
                    "message": "image_data must be a data URL (data:image/...)",
                }
            },
        )

    emitter = SSEEmitter()
    run_id = uuid4()

    ctx = copy_context()
    ctx.run(heartbeat_emitter.set, make_progress_emitter(emitter, run_id))

    artifact_store: ArtifactStore = request.app.state.artifact_store

    handler_task = asyncio.create_task(
        _run_handler(body, session, emitter, run_id, artifact_store),
        name=f"dashboard-handler-{run_id}",
        context=ctx,
    )

    async def cleanup_wrapper() -> AsyncIterator[bytes]:
        try:
            async for frame in emitter.stream():
                yield frame
        finally:
            if not handler_task.done():
                handler_task.cancel()

    return StreamingResponse(
        cleanup_wrapper(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-store", "X-Run-Id": str(run_id)},
    )


async def _run_handler(
    body: DashboardRequest,
    session: SessionContext,
    emitter: SSEEmitter,
    run_id: UUID,
    artifact_store: ArtifactStore,
) -> None:
    from ..workflow import step_dashboard

    try:
        await step_dashboard.run(
            request=body,
            session=session,
            emitter=emitter,
            run_id=run_id,
            artifact_store=artifact_store,
        )
    except asyncio.CancelledError:
        emitter.emit(ErrorEvent(
            run_id=run_id, code="cancelled", message="Cancelled.", retriable=False
        ))
        raise
    except Exception as exc:
        logger.exception("dashboard handler failed: %s", exc)
        emitter.emit(ErrorEvent(
            run_id=run_id, code="agent_error",
            message=f"{type(exc).__name__}: {exc}", retriable=True,
        ))
    finally:
        emitter.close()
