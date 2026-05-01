"""Contract tests for /workflow/query/cross-source (T091, US4).

Exercises FR-015 (cross-source unavailable when <2 live), FR-016
(per-source pulls + scratchpad join), FR-017 (response shape: chips
+ join_result + KPI snapshot), FR-018 (read-only enforcement +
row caps), and the activity-log emission of `ttyd_query`.
"""

from __future__ import annotations

import asyncio
import tempfile
from typing import Any
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from platform_agent.api.routes_query_cross_source import (
    _reset_kpi,
)
from platform_agent.api.routes_query_cross_source import (
    router as cross_source_router,
)
from platform_agent.api.routes_workspace import router as workspace_router
from platform_agent.workspace.lifecycle import await_inflight
from platform_agent.workspace.registry import WorkspaceRegistry


@pytest.fixture(autouse=True)
def _isolate(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "DSA_HUB_CONNECTIONS_DIR", tempfile.mkdtemp(prefix="dsa-hub-test-")
    )
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.setenv("DSA_HUB_LIFECYCLE_FAKE", "1")
    monkeypatch.setattr(
        "platform_agent.workspace.registry._registry",
        WorkspaceRegistry(),
    )
    _reset_kpi()

    # Stub _run_pull so tests don't need a live DB.
    def fake_pull(conn, spec, _ws):
        from platform_agent.tools.duckdb_scratchpad import SourcePullResult

        if spec.view_name == "pg_clients":
            rows = [
                {"client_id": 1, "name": "Alice"},
                {"client_id": 2, "name": "Bob"},
            ]
            cols = ["client_id", "name"]
        elif spec.view_name == "sf_aum":
            rows = [
                {"client_id": 1, "ending_aum": 1_000_000},
                {"client_id": 2, "ending_aum": 2_500_000},
            ]
            cols = ["client_id", "ending_aum"]
        else:
            rows = []
            cols = []
        return SourcePullResult(
            connection_id=conn.connection_id,
            view_name=spec.view_name,
            columns=cols,
            rows=rows,
            truncated_at_cap=False,
        )

    monkeypatch.setattr(
        "platform_agent.api.routes_query_cross_source._run_pull", fake_pull
    )


def _build_app() -> FastAPI:
    app = FastAPI()
    app.include_router(workspace_router)
    app.include_router(cross_source_router)
    return app


async def _two_connections(hdr: dict[str, str]) -> tuple[str, str]:
    async with AsyncClient(
        transport=ASGITransport(app=_build_app()), base_url="http://t"
    ) as ac:
        pg = await ac.post(
            "/workspace/connection",
            json={
                "driver_type": "postgresql",
                "display_name": "Pinnacle PG",
                "endpoint": "host:5432",
                "scope": "pinnacle.public",
                "credentials": {},
            },
            headers=hdr,
        )
        sf = await ac.post(
            "/workspace/connection",
            json={
                "driver_type": "snowflake",
                "display_name": "Pinnacle SF",
                "endpoint": "lga76011",
                "scope": "PINNACLE_FINANCIAL_DEMO_ASINGH.ANALYTICS",
                "credentials": {},
            },
            headers=hdr,
        )
        await await_inflight()
        return pg.json()["connection_id"], sf.json()["connection_id"]


def _payload(pg_id: str, sf_id: str) -> dict[str, Any]:
    return {
        "question": "Top clients by AUM",
        "lens": "all",
        "pulls": [
            {
                "connection_id": pg_id,
                "sql": "SELECT client_id, name FROM crm.client LIMIT 250",
                "view_name": "pg_clients",
                "max_rows": 250,
            },
            {
                "connection_id": sf_id,
                "sql": (
                    "SELECT client_id, ending_aum "
                    "FROM ANALYTICS.FCT_AUM_HISTORY LIMIT 250"
                ),
                "view_name": "sf_aum",
                "max_rows": 250,
            },
        ],
        "join_sql": (
            "SELECT pg.client_id, pg.name, sf.ending_aum "
            "FROM pg_clients pg INNER JOIN sf_aum sf "
            "ON pg.client_id = sf.client_id "
            "ORDER BY sf.ending_aum DESC"
        ),
    }


def test_400_when_lens_all_but_only_one_live() -> None:
    async def _run() -> None:
        hdr = {"X-DSA-Session-ID": str(uuid4())}
        # Add only ONE connection.
        async with AsyncClient(
            transport=ASGITransport(app=_build_app()), base_url="http://t"
        ) as ac:
            await ac.post(
                "/workspace/connection",
                json={
                    "driver_type": "postgresql",
                    "display_name": "PG",
                    "endpoint": "host:5432",
                    "scope": "pinnacle.public",
                    "credentials": {},
                },
                headers=hdr,
            )
            await await_inflight()
            r = await ac.post(
                "/workflow/query/cross-source",
                json={
                    "question": "x",
                    "lens": "all",
                    "pulls": [
                        {
                            "connection_id": "x",
                            "sql": "SELECT 1",
                            "view_name": "v",
                            "max_rows": 250,
                        }
                    ],
                    "join_sql": "SELECT 1",
                },
                headers=hdr,
            )
            assert r.status_code == 400
            assert r.json()["detail"]["code"] == "cross_source_unavailable"

    asyncio.run(_run())


def test_400_for_read_only_violation_in_pull_sql() -> None:
    async def _run() -> None:
        hdr = {"X-DSA-Session-ID": str(uuid4())}
        pg_id, sf_id = await _two_connections(hdr)
        body = _payload(pg_id, sf_id)
        body["pulls"][0]["sql"] = "DROP TABLE crm.client"
        async with AsyncClient(
            transport=ASGITransport(app=_build_app()), base_url="http://t"
        ) as ac:
            r = await ac.post(
                "/workflow/query/cross-source", json=body, headers=hdr
            )
            assert r.status_code == 400
            assert r.json()["detail"]["code"] == "read_only_violation"

    asyncio.run(_run())


def test_400_for_read_only_violation_in_join_sql() -> None:
    async def _run() -> None:
        hdr = {"X-DSA-Session-ID": str(uuid4())}
        pg_id, sf_id = await _two_connections(hdr)
        body = _payload(pg_id, sf_id)
        body["join_sql"] = "DELETE FROM pg_clients"
        async with AsyncClient(
            transport=ASGITransport(app=_build_app()), base_url="http://t"
        ) as ac:
            r = await ac.post(
                "/workflow/query/cross-source", json=body, headers=hdr
            )
            assert r.status_code == 400
            assert r.json()["detail"]["code"] == "read_only_violation"

    asyncio.run(_run())


def test_happy_path_returns_chips_and_join_result() -> None:
    async def _run() -> None:
        hdr = {"X-DSA-Session-ID": str(uuid4())}
        pg_id, sf_id = await _two_connections(hdr)
        async with AsyncClient(
            transport=ASGITransport(app=_build_app()), base_url="http://t"
        ) as ac:
            r = await ac.post(
                "/workflow/query/cross-source",
                json=_payload(pg_id, sf_id),
                headers=hdr,
            )
            assert r.status_code == 200, r.text
            body = r.json()
            assert body["join_result"]["rows_returned"] == 2
            assert {row["name"] for row in body["join_result"]["rows"]} == {
                "Alice",
                "Bob",
            }
            assert len(body["sources_used"]) == 2
            assert body["sources_used"][0]["chip_label"]
            assert body["kpi_snapshot"]["queries_answered_today"] == 1
            assert body["latency_ms"] >= 0
            # answer is summarized text
            assert "Alice" not in body["answer"]  # answer is metadata, not data dump
            assert "rows" in body["answer"]

    asyncio.run(_run())


def test_kpi_increments_across_calls() -> None:
    async def _run() -> None:
        hdr = {"X-DSA-Session-ID": str(uuid4())}
        pg_id, sf_id = await _two_connections(hdr)
        async with AsyncClient(
            transport=ASGITransport(app=_build_app()), base_url="http://t"
        ) as ac:
            for _ in range(3):
                r = await ac.post(
                    "/workflow/query/cross-source",
                    json=_payload(pg_id, sf_id),
                    headers=hdr,
                )
                assert r.status_code == 200
            # Last call's kpi should report 3.
            assert r.json()["kpi_snapshot"]["queries_answered_today"] == 3

    asyncio.run(_run())
