"""Contract tests for /workspace/* endpoints (T032).

Exercises POST/DELETE/GET /workspace/connection(s), POST retry, and
GET /workspace/kpis per `contracts/workspace.openapi.yaml`.
Lifecycle uses DSA_HUB_LIFECYCLE_FAKE=1 so the worker advances to
`live` without hitting a real database.
"""

from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from platform_agent.api.routes_workspace import router as workspace_router
from platform_agent.workspace.lifecycle import await_inflight
from platform_agent.workspace.registry import WorkspaceRegistry


@pytest.fixture(autouse=True)
def _isolate_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    """Each test gets a fresh in-memory WorkspaceRegistry — no cross-test bleed."""
    fresh = WorkspaceRegistry()
    monkeypatch.setattr(
        "platform_agent.workspace.registry._registry",
        fresh,
    )
    monkeypatch.setenv("DSA_HUB_LIFECYCLE_FAKE", "1")


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.include_router(workspace_router)
    return TestClient(app)


def _hdr() -> dict[str, str]:
    return {"X-DSA-Session-ID": str(uuid4())}


def _add_payload(**overrides) -> dict[str, object]:
    base = {
        "driver_type": "postgresql",
        "display_name": "Pinnacle PG",
        "endpoint": "host.example.com:5432",
        "scope": "pinnacle.public",
        "credentials": {"user": "postgres", "password": "x"},
        "tags": ["pinnacle"],
    }
    base.update(overrides)
    return base


# ───── Header / auth ─────


def test_add_connection_requires_session_header(client: TestClient) -> None:
    r = client.post("/workspace/connection", json=_add_payload())
    assert r.status_code == 400
    assert "X-DSA-Session-ID" in r.json()["detail"]


def test_workspace_id_alias_accepted(client: TestClient) -> None:
    r = client.get(
        "/workspace/connections",
        headers={"X-DSA-Workspace-ID": str(uuid4())},
    )
    assert r.status_code == 200


# ───── Add connection happy path ─────


def test_add_connection_creates_201(client: TestClient) -> None:
    r = client.post("/workspace/connection", json=_add_payload(), headers=_hdr())
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "connecting"
    assert len(body["connection_id"]) == 64  # SHA-256 hex
    assert body["display_name"] == "Pinnacle PG"


def test_add_connection_lifecycle_progresses_to_live() -> None:
    """End-to-end via the AsyncClient so the lifecycle Task can run."""

    async def _scenario() -> None:
        from httpx import ASGITransport, AsyncClient

        app = FastAPI()
        app.include_router(workspace_router)

        hdr = _hdr()
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t"
        ) as ac:
            r = await ac.post("/workspace/connection", json=_add_payload(), headers=hdr)
            assert r.status_code == 201
            await await_inflight()
            r = await ac.get("/workspace/connections", headers=hdr)
            assert r.status_code == 200
            connections = r.json()["connections"]
            assert len(connections) == 1
            assert connections[0]["status"] == "live"
            assert connections[0]["kpis"]["tables_total"] == 14
            assert connections[0]["kpis"]["processes_detected"] == 8

    asyncio.run(_scenario())


# ───── Duplicate / 409 ─────


def test_add_duplicate_returns_409(client: TestClient) -> None:
    h = _hdr()
    r1 = client.post("/workspace/connection", json=_add_payload(), headers=h)
    assert r1.status_code == 201
    r2 = client.post("/workspace/connection", json=_add_payload(), headers=h)
    assert r2.status_code == 409
    assert r2.json()["detail"]["code"] == "duplicate_connection"


def test_validation_error_returns_422(client: TestClient) -> None:
    r = client.post(
        "/workspace/connection",
        json=_add_payload(driver_type="oracle"),  # not in enum
        headers=_hdr(),
    )
    assert r.status_code == 422


# ───── List ─────


def test_list_connections_empty(client: TestClient) -> None:
    r = client.get("/workspace/connections", headers=_hdr())
    assert r.status_code == 200
    assert r.json() == {"connections": []}


def test_list_connections_after_add(client: TestClient) -> None:
    h = _hdr()
    client.post("/workspace/connection", json=_add_payload(), headers=h)
    client.post(
        "/workspace/connection",
        json=_add_payload(
            driver_type="snowflake",
            display_name="Pinnacle SF",
            endpoint="lga76011",
            scope="PINNACLE_FINANCIAL_DEMO_ASINGH.ANALYTICS",
        ),
        headers=h,
    )
    r = client.get("/workspace/connections", headers=h)
    assert r.status_code == 200
    body = r.json()
    assert len(body["connections"]) == 2
    assert {c["driver_type"] for c in body["connections"]} == {"postgresql", "snowflake"}


# ───── Delete ─────


def test_delete_connection_returns_204(client: TestClient) -> None:
    h = _hdr()
    add = client.post("/workspace/connection", json=_add_payload(), headers=h).json()
    r = client.delete(f"/workspace/connection/{add['connection_id']}", headers=h)
    assert r.status_code == 204
    listing = client.get("/workspace/connections", headers=h).json()
    assert listing["connections"] == []


def test_delete_unknown_connection_returns_404(client: TestClient) -> None:
    r = client.delete("/workspace/connection/not-a-real-id", headers=_hdr())
    assert r.status_code == 404


# ───── Retry ─────


def test_retry_unknown_connection_returns_404(client: TestClient) -> None:
    r = client.post("/workspace/connection/not-a-real-id/retry", headers=_hdr())
    assert r.status_code == 404


def test_retry_resets_status_to_connecting() -> None:
    async def _scenario() -> None:
        from httpx import ASGITransport, AsyncClient

        app = FastAPI()
        app.include_router(workspace_router)
        hdr = _hdr()
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t"
        ) as ac:
            add = (await ac.post(
                "/workspace/connection", json=_add_payload(), headers=hdr
            )).json()
            await await_inflight()
            cid = add["connection_id"]
            # Force the connection into error state, then retry.
            from uuid import UUID

            from platform_agent.workspace.models import ConnectionError, ConnectionStatus
            from platform_agent.workspace.registry import get_registry

            ws_id = UUID(hdr["X-DSA-Session-ID"])
            get_registry().update_connection(
                ws_id,
                cid,
                status=ConnectionStatus.ERROR,
                error=ConnectionError(code="x", message="y", retryable=True),
            )
            r = await ac.post(f"/workspace/connection/{cid}/retry", headers=hdr)
            assert r.status_code == 200
            assert r.json()["status"] == "connecting"
            await await_inflight()
            listing = (await ac.get("/workspace/connections", headers=hdr)).json()
            assert listing["connections"][0]["status"] == "live"

    asyncio.run(_scenario())


# ───── KPIs ─────


def test_kpis_empty_workspace(client: TestClient) -> None:
    r = client.get("/workspace/kpis", headers=_hdr())
    assert r.status_code == 200
    assert r.json()["sources_connected"] == 0


def test_kpis_aggregate_after_two_live_connections() -> None:
    async def _scenario() -> None:
        from httpx import ASGITransport, AsyncClient

        app = FastAPI()
        app.include_router(workspace_router)
        hdr = _hdr()
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t"
        ) as ac:
            await ac.post("/workspace/connection", json=_add_payload(), headers=hdr)
            await ac.post(
                "/workspace/connection",
                json=_add_payload(
                    driver_type="snowflake",
                    display_name="Pinnacle SF",
                    endpoint="lga76011",
                    scope="PINNACLE_FINANCIAL_DEMO_ASINGH.ANALYTICS",
                ),
                headers=hdr,
            )
            await await_inflight()
            r = await ac.get("/workspace/kpis", headers=hdr)
            assert r.status_code == 200
            kpi = r.json()
            # Both fake-lifecycle connections reach `live` with tables_total=14
            # and rows_estimated=15415 each.
            assert kpi["sources_connected"] == 2
            assert kpi["tables_total"] == 28
            assert kpi["rows_total"] == 15415 * 2

    asyncio.run(_scenario())
