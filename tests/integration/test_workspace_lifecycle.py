"""Integration test: full multi-source workspace lifecycle (T033, US1).

Drives the workspace from "no connections" → "two connections live"
through the real FastAPI app + lifecycle worker, asserting:
- KPI strip aggregates across both live connections
- Lens selector exposes "all" plus per-source entries (covered via
  the connection list shape that drives the frontend lens hook)
- Duplicate `(driver_type, endpoint, scope)` is a 409
- Activity log captures `connection_added` + `connection_retried` etc.

Uses DSA_HUB_LIFECYCLE_FAKE=1 so the worker never touches a real DB.
"""

from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from platform_agent.workspace.activity_log import snapshot as log_snapshot
from platform_agent.workspace.activity_models import ActivityKind
from platform_agent.workspace.lifecycle import await_inflight
from platform_agent.workspace.registry import WorkspaceRegistry


@pytest.fixture(autouse=True)
def _isolate(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DSA_HUB_LIFECYCLE_FAKE", "1")
    monkeypatch.setattr(
        "platform_agent.workspace.registry._registry",
        WorkspaceRegistry(),
    )


def _build_app():
    from fastapi import FastAPI

    from platform_agent.api.routes_workspace import router as workspace_router

    app = FastAPI()
    app.include_router(workspace_router)
    return app


def test_full_workspace_lifecycle_two_connections() -> None:
    async def _scenario() -> None:
        ws_id = uuid4()
        hdr = {"X-DSA-Session-ID": str(ws_id)}

        async with AsyncClient(
            transport=ASGITransport(app=_build_app()), base_url="http://t"
        ) as ac:
            # 1. Add Postgres
            r = await ac.post(
                "/workspace/connection",
                json={
                    "driver_type": "postgresql",
                    "display_name": "Pinnacle PG",
                    "endpoint": "platform-agent-pinnacle.example:5432",
                    "scope": "pinnacle.public",
                    "credentials": {"user": "postgres"},
                },
                headers=hdr,
            )
            assert r.status_code == 201
            assert r.json()["status"] == "connecting"

            # 2. Add Snowflake
            r = await ac.post(
                "/workspace/connection",
                json={
                    "driver_type": "snowflake",
                    "display_name": "Pinnacle SF",
                    "endpoint": "lga76011",
                    "scope": "PINNACLE_FINANCIAL_DEMO_ASINGH.ANALYTICS",
                    "credentials": {"authenticator": "externalbrowser"},
                },
                headers=hdr,
            )
            assert r.status_code == 201

            # 3. Wait for both lifecycles to finish
            await await_inflight()

            # 4. List → both live; the data shape drives the lens selector
            #    (frontend builds `all + per-connection` from this list).
            r = await ac.get("/workspace/connections", headers=hdr)
            connections = r.json()["connections"]
            assert len(connections) == 2
            assert all(c["status"] == "live" for c in connections)
            display_names = {c["display_name"] for c in connections}
            assert display_names == {"Pinnacle PG", "Pinnacle SF"}

            # 5. KPI strip aggregates across live connections
            r = await ac.get("/workspace/kpis", headers=hdr)
            kpis = r.json()
            assert kpis["sources_connected"] == 2
            assert kpis["tables_total"] == 28  # 14 + 14 from fake lifecycle
            assert kpis["processes_detected"] == 16  # 8 + 8

            # 6. Activity log captured connection_added × 2
            entries = [e for e in log_snapshot() if e.workspace_id == ws_id]
            kinds = [e.kind for e in entries]
            assert kinds.count(ActivityKind.CONNECTION_ADDED) == 2

    asyncio.run(_scenario())


def test_duplicate_connection_is_409() -> None:
    async def _scenario() -> None:
        hdr = {"X-DSA-Session-ID": str(uuid4())}
        payload = {
            "driver_type": "postgresql",
            "display_name": "Pinnacle PG",
            "endpoint": "host:5432",
            "scope": "pinnacle.public",
            "credentials": {},
        }
        async with AsyncClient(
            transport=ASGITransport(app=_build_app()), base_url="http://t"
        ) as ac:
            r1 = await ac.post("/workspace/connection", json=payload, headers=hdr)
            assert r1.status_code == 201
            r2 = await ac.post("/workspace/connection", json=payload, headers=hdr)
            assert r2.status_code == 409
            assert r2.json()["detail"]["code"] == "duplicate_connection"
            # listing unchanged
            r = await ac.get("/workspace/connections", headers=hdr)
            assert len(r.json()["connections"]) == 1

    asyncio.run(_scenario())


def test_two_tabs_do_not_share_state() -> None:
    """Q1 invariant: each per-tab session UUID has its own workspace."""

    async def _scenario() -> None:
        async with AsyncClient(
            transport=ASGITransport(app=_build_app()), base_url="http://t"
        ) as ac:
            # Tab A
            hdr_a = {"X-DSA-Session-ID": str(uuid4())}
            await ac.post(
                "/workspace/connection",
                json={
                    "driver_type": "postgresql",
                    "display_name": "Tab A PG",
                    "endpoint": "host:5432",
                    "scope": "pinnacle.public",
                    "credentials": {},
                },
                headers=hdr_a,
            )
            # Tab B (different session UUID) sees nothing.
            hdr_b = {"X-DSA-Session-ID": str(uuid4())}
            r = await ac.get("/workspace/connections", headers=hdr_b)
            assert r.json() == {"connections": []}
            # Tab A still has its connection.
            r = await ac.get("/workspace/connections", headers=hdr_a)
            assert len(r.json()["connections"]) == 1

    asyncio.run(_scenario())
