"""POST /workflow/step, GET /workflow/artifact/{handle}, POST /workflow/cancel.

Entry point for the DSA 4-step frontend. Implements ADR-015 D8 (FastAPI
dispatcher), D10 (two-phase zip delivery), D11 (session header), D14
(SSE schema v1), and D16 (memory_unreachable surface).

Per-step handlers live under :mod:`platform_agent.workflow`. They receive a
:class:`StepRequest`, the request's :class:`SessionContext`, and an
:class:`SSEEmitter`. They are expected to emit a stream of events ending in
exactly one terminal event (``done`` / ``error`` / ``artifact_ready``).
"""

from __future__ import annotations

import asyncio
import io
import logging
import zipfile
from collections.abc import AsyncIterator
from contextvars import copy_context
from typing import Annotated, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..session.memory_adapter import MemoryUnavailable
from ..workflow.steps import STEP_REGISTRY, StepId
from .deps import SessionContext, get_session_context
from .events import ErrorEvent
from .sse import SSEEmitter, heartbeat_emitter, make_progress_emitter
from .zip_stream import ArtifactStore

logger = logging.getLogger(__name__)

router = APIRouter()


# ───────── Request models ─────────


class PasswordCredential(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["password"] = "password"
    password: str

    # Strip leading/trailing whitespace on password — copy-paste artifacts
    # (trailing newline from a clipboard, leading tab from a secret manager
    # export) were producing silent "password authentication failed" loops.
    # A password that legitimately begins or ends with whitespace is an
    # extraordinarily rare edge case and not worth protecting against.
    @field_validator("password", mode="before")
    @classmethod
    def _trim_password(cls, v: object) -> object:
        if isinstance(v, str):
            return v.strip()
        return v


class SSOExternalBrowserCredential(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["sso_externalbrowser"] = "sso_externalbrowser"


Credential = PasswordCredential | SSOExternalBrowserCredential


import re

_ALL_WS = re.compile(r"\s+")


def _trim(v: str | None) -> str | None:
    """Strip leading/trailing whitespace; treat empty results as None."""
    if v is None:
        return None
    stripped = v.strip()
    return stripped or None


def _strip_all_ws(v: str | None) -> str | None:
    """Remove every whitespace character (DNS names and account IDs can't have any)."""
    if v is None:
        return None
    cleaned = _ALL_WS.sub("", v)
    return cleaned or None


def _trim_required(v: str) -> str:
    """Strip whitespace; reject empty results (raises for required fields)."""
    stripped = v.strip()
    if not stripped:
        raise ValueError("value is empty after trimming whitespace")
    return stripped


class SourceConnection(BaseModel):
    # Suppress Pydantic's "schema" shadow warning; we keep `schema` as the
    # field name to match the wire contract documented in data-model.md §3.
    model_config = ConfigDict(extra="forbid", protected_namespaces=())
    driver_type: Literal["postgresql", "redshift", "snowflake"]
    host: str | None = None
    account: str | None = None
    port: int | None = Field(default=None, ge=1, le=65535)
    database: str
    schema: str | None = None  # type: ignore[assignment]  # shadows BaseModel.schema by design
    user: str
    role: str | None = None
    warehouse: str | None = None
    credential: Credential

    # Auto-sanitize string fields so copy-paste artifacts (leading/trailing
    # spaces, tabs, embedded spaces from wrapped URLs, etc.) don't reach the
    # driver. psycopg2 rejects hostnames with any embedded whitespace with a
    # confusing "could not translate host name" error.
    #
    # host/account: strip ALL whitespace (DNS names and Snowflake account IDs
    # cannot legally contain whitespace anywhere).
    # schema/role/warehouse: edge-trim only (these CAN contain valid chars we
    # don't want to strip).
    # database/user: edge-trim + reject empty (required fields).
    @field_validator("host", "account", mode="before")
    @classmethod
    def _clean_hostlike(cls, v: object) -> object:
        return _strip_all_ws(v) if isinstance(v, str) else v

    @field_validator("schema", "role", "warehouse", mode="before")
    @classmethod
    def _trim_optional(cls, v: object) -> object:
        return _trim(v) if isinstance(v, str) else v

    @field_validator("database", "user", mode="before")
    @classmethod
    def _trim_required_field(cls, v: object) -> object:
        return _trim_required(v) if isinstance(v, str) else v


class StepRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    step_id: StepId
    user_message: Annotated[str, Field(min_length=1, max_length=4000)]
    prior_artifact: dict | None = None
    connection: SourceConnection | None = None
    resume: bool = False


class CancelRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session_id: UUID
    run_id: UUID


class CancelResponse(BaseModel):
    cancelled: bool


# ───────── Active-run registry (for cancel) ─────────


class _RunRegistry:
    """Tracks in-flight (run_id → asyncio.Task) so POST /workflow/cancel can abort."""

    def __init__(self) -> None:
        self._runs: dict[UUID, asyncio.Task] = {}
        self._lock = asyncio.Lock()

    async def register(self, run_id: UUID, task: asyncio.Task) -> None:
        async with self._lock:
            self._runs[run_id] = task

    async def cancel(self, run_id: UUID) -> bool:
        async with self._lock:
            task = self._runs.pop(run_id, None)
        if task is None:
            return False
        task.cancel()
        return True

    async def remove(self, run_id: UUID) -> None:
        async with self._lock:
            self._runs.pop(run_id, None)


_registry = _RunRegistry()


# ───────── POST /workflow/step ─────────


@router.post("/workflow/step")
async def post_step(
    request: Request,
    body: StepRequest,
    session: SessionContext = Depends(get_session_context),
) -> StreamingResponse:
    """Dispatch a step. Returns a long-lived SSE stream ending in one terminal event."""

    config = STEP_REGISTRY[body.step_id]
    if config.require_db_connection and body.connection is None:
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": "validation_error",
                    "message": f"Step {body.step_id} requires a database connection",
                    "field": "connection",
                }
            },
        )

    emitter = SSEEmitter()
    run_id = uuid4()

    # Bind the heartbeat emitter for the duration of the handler so
    # @tool functions can push tool_progress events. copy_context() isolates
    # this bind from concurrent requests.
    ctx = copy_context()
    ctx.run(heartbeat_emitter.set, make_progress_emitter(emitter, run_id))

    artifact_store: ArtifactStore = request.app.state.artifact_store

    handler_task = asyncio.create_task(
        _run_handler(body, session, emitter, run_id, artifact_store),
        name=f"step-handler-{run_id}",
        context=ctx,
    )
    await _registry.register(run_id, handler_task)

    async def cleanup_wrapper() -> AsyncIterator[bytes]:
        try:
            async for frame in emitter.stream():
                yield frame
        finally:
            await _registry.remove(run_id)
            if not handler_task.done():
                handler_task.cancel()

    return StreamingResponse(
        cleanup_wrapper(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-store", "X-Run-Id": str(run_id)},
    )


async def _run_handler(
    body: StepRequest,
    session: SessionContext,
    emitter: SSEEmitter,
    run_id: UUID,
    artifact_store: ArtifactStore,
) -> None:
    """Invoke the step-specific handler; translate exceptions into terminal events."""

    # Deferred imports so the module can be loaded before step handler bodies exist.
    from ..workflow import step_1_requirements, step_2_conceptual, step_3_logical, step_4_detailed

    handler_map = {
        StepId.REQUIREMENTS: step_1_requirements.run,
        StepId.CONCEPTUAL: step_2_conceptual.run,
        StepId.LOGICAL: step_3_logical.run,
        StepId.DETAILED: step_4_detailed.run,
    }
    handler = handler_map[body.step_id]

    try:
        await handler(
            request=body,
            session=session,
            emitter=emitter,
            run_id=run_id,
            artifact_store=artifact_store,
        )
    except asyncio.CancelledError:
        emitter.emit(
            ErrorEvent(
                run_id=run_id,
                code="cancelled",
                message="Step was cancelled by the user.",
                retriable=False,
            )
        )
        raise
    except MemoryUnavailable as exc:
        logger.warning("memory_unreachable: %s", exc)
        emitter.emit(
            ErrorEvent(
                run_id=run_id,
                code="memory_unreachable",
                message=(
                    "Conversation memory is unavailable; your session will not survive a refresh."
                ),
                retriable=True,
            )
        )
    except Exception as exc:
        logger.exception("step handler failed: %s", exc)
        emitter.emit(
            ErrorEvent(
                run_id=run_id,
                code="agent_error",
                message=f"{type(exc).__name__}: {exc}",
                retriable=True,
            )
        )
    finally:
        emitter.close()


# ───────── GET /workflow/artifact/{handle} ─────────


@router.get("/workflow/artifact/{handle}")
async def get_artifact(
    handle: UUID,
    request: Request,
    session: SessionContext = Depends(get_session_context),
) -> StreamingResponse:
    """Download a previously-prepared zip by handle (single-use, 60 s TTL)."""

    store: ArtifactStore = request.app.state.artifact_store
    zip_bytes = await store.consume(handle, session.session_id)
    if zip_bytes is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    filename = f"dbt-project-{handle}.zip"
    return StreamingResponse(
        io.BytesIO(zip_bytes),
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
        },
    )


# ───────── POST /workflow/cancel ─────────


@router.post("/workflow/cancel", response_model=CancelResponse)
async def post_cancel(
    body: CancelRequest,
    _session: SessionContext = Depends(get_session_context),
) -> CancelResponse:
    cancelled = await _registry.cancel(body.run_id)
    return CancelResponse(cancelled=cancelled)


__all__ = ["router", "StepRequest", "SourceConnection"]


# Helper used by tests: build an in-memory zip from a file-tree dict.
def zip_from_dir(project_root: str) -> bytes:
    """Zip the contents of ``project_root`` (absolute path) into memory."""
    from pathlib import Path

    buf = io.BytesIO()
    root = Path(project_root)
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in root.rglob("*"):
            if path.is_file():
                zf.write(path, arcname=str(path.relative_to(root.parent)))
    return buf.getvalue()
