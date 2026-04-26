"""FastAPI app — thin HTTP/SSE layer in front of the Strands agent.

Mounts /health immediately; /workflow/* routes land in T035. Starts the zip-store
sweeper on startup and tears it down on shutdown.

Run locally:
    uv run uvicorn platform_agent.api.app:app --host 0.0.0.0 --port 8080 --reload
"""

from __future__ import annotations

import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routes_discover import router as discover_router
from .routes_health import router as health_router
from .routes_query import router as query_router
from .routes_workflow import router as workflow_router
from .routes_workflow_provision import router as workflow_provision_router
from .routes_workspace import router as workspace_router
from .routes_workspace_discover import router as workspace_discover_router
from .zip_stream import ArtifactStore

logger = logging.getLogger(__name__)


def _cors_origins() -> list[str]:
    # Cover both 127.0.0.1 and localhost on Vite's default port — they are
    # distinct origins to the browser and prior preflights silently failed
    # when the user opened the app via the address Vite didn't print.
    default = "http://localhost:5173,http://127.0.0.1:5173"
    raw = os.environ.get("CORS_ALLOWED_ORIGINS", default)
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Start/stop background tasks that live as long as the app does."""
    store = ArtifactStore()
    app.state.artifact_store = store
    await store.start_sweeper()
    try:
        yield
    finally:
        await store.stop_sweeper()


def create_app() -> FastAPI:
    app = FastAPI(
        title="DSA Platform Agent API",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins(),
        allow_credentials=False,
        # DELETE added for /workspace/connection/{id} (002-dsa-hub-pinnacle US1).
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=[
            "Content-Type",
            "Accept",
            "Authorization",
            "X-DSA-Session-ID",
            # 002-dsa-hub-pinnacle FR-006 — back-compat alias for one minor version.
            "X-DSA-Workspace-ID",
        ],
    )

    app.include_router(health_router)
    app.include_router(workflow_router)
    app.include_router(query_router)
    app.include_router(discover_router)
    app.include_router(workspace_router)
    app.include_router(workspace_discover_router)
    app.include_router(workflow_provision_router)

    return app


app = create_app()
