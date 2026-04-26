"""Contract tests for /workflow/pills + /workflow/pills/{id}/draft-prd (T048).

Asserts FR-011 (≥6 schema-grounded pills), FR-012 (six named Pinnacle
pills present when both Pinnacle sources are live), and FR-013
(clicking a pill returns a complete PRD draft with target / joins /
business questions / standards-applied footer).
"""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import uuid4

import pytest
from fastapi import FastAPI

from platform_agent.api.routes_workspace import router as workspace_router
from platform_agent.api.routes_workspace_discover import (
    _reset_caches,
)
from platform_agent.api.routes_workspace_discover import (
    router as discover_router,
)
from platform_agent.workspace.lifecycle import await_inflight
from platform_agent.workspace.registry import WorkspaceRegistry


def _pinnacle_pg_metadata() -> dict[str, Any]:
    # Reuse the schema layout from test_discover_workspace, condensed.
    schemas: dict[str, list[tuple[str, list[str], int]]] = {
        "ap": [("ap_invoice", ["invoice_id", "client_id", "amount"], 336)],
        "billing": [("fee_invoice", ["invoice_id", "client_id", "account_id"], 1680)],
        "crm": [("client", ["client_id", "name"], 35)],
        "gl": [("JOURNAL_ENTRY", ["entry_id", "period_id"], 69)],
        "hr": [("employee", ["employee_id", "department_id"], 15)],
        "performance": [
            ("account_aum_daily", ["snapshot_id", "account_id", "client_id"], 6300),
        ],
        "planning": [("budget_line", ["line_id", "period_id"], 480)],
        "portfolio": [("trade", ["trade_id", "account_id", "client_id"], 420)],
    }
    tables: list[dict[str, Any]] = []
    for schema, rows in schemas.items():
        for tbl, columns, rc in rows:
            tables.append(
                {
                    "schema": schema,
                    "table_name": tbl,
                    "fully_qualified_name": f"pinnacle.{schema}.{tbl}",
                    "columns": [{"column_name": c, "data_type": "text"} for c in columns],
                    "primary_key": [columns[0]],
                    "foreign_keys": [],
                    "row_count": rc,
                }
            )
    return {
        "source_id": "postgresql_pinnacle",
        "service": "postgresql",
        "database": "pinnacle",
        "schemas": list(schemas.keys()),
        "tables": tables,
    }


def _snowflake_analytical_metadata() -> dict[str, Any]:
    return {
        "source_id": "snowflake_pinnacle",
        "service": "snowflake",
        "database": "PINNACLE_FINANCIAL_DEMO_ASINGH",
        "schemas": ["ANALYTICS"],
        "tables": [
            {
                "schema": "ANALYTICS",
                "table_name": "FCT_AUM_HISTORY",
                "fully_qualified_name": (
                    "PINNACLE_FINANCIAL_DEMO_ASINGH.ANALYTICS.FCT_AUM_HISTORY"
                ),
                "columns": [
                    {"column_name": c, "data_type": "varchar"}
                    for c in ["snapshot_date", "account_id", "client_id", "ending_aum"]
                ],
                "primary_key": [],
                "foreign_keys": [],
                "row_count": 6300,
            }
        ],
    }


@pytest.fixture(autouse=True)
def _isolate(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "platform_agent.workspace.registry._registry",
        WorkspaceRegistry(),
    )
    monkeypatch.setenv("DSA_HUB_LIFECYCLE_FAKE", "1")
    _reset_caches()

    def fake_scan(conn, _ws):
        if conn.driver_type.value == "postgresql":
            return _pinnacle_pg_metadata()
        if conn.driver_type.value == "snowflake":
            return _snowflake_analytical_metadata()
        return {"tables": [], "schemas": [], "database": "x"}

    monkeypatch.setattr(
        "platform_agent.api.routes_workspace_discover._scan_connection",
        fake_scan,
    )


def _build_app() -> FastAPI:
    app = FastAPI()
    app.include_router(workspace_router)
    app.include_router(discover_router)
    return app


async def _seed_two_connections(hdr: dict[str, str]) -> None:
    from httpx import ASGITransport, AsyncClient

    async with AsyncClient(
        transport=ASGITransport(app=_build_app()), base_url="http://t"
    ) as ac:
        await ac.post(
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
        await ac.post(
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


def test_pills_400_no_live_connections() -> None:
    async def _run() -> None:
        from httpx import ASGITransport, AsyncClient

        hdr = {"X-DSA-Session-ID": str(uuid4())}
        async with AsyncClient(
            transport=ASGITransport(app=_build_app()), base_url="http://t"
        ) as ac:
            r = await ac.post("/workflow/pills", json={}, headers=hdr)
            assert r.status_code == 400
            assert r.json()["detail"]["code"] == "no_live_connections"

    asyncio.run(_run())


def test_pills_returns_six_named_pinnacle_pills() -> None:
    async def _run() -> None:
        from httpx import ASGITransport, AsyncClient

        hdr = {"X-DSA-Session-ID": str(uuid4())}
        await _seed_two_connections(hdr)
        async with AsyncClient(
            transport=ASGITransport(app=_build_app()), base_url="http://t"
        ) as ac:
            r = await ac.post("/workflow/pills", json={}, headers=hdr)
            assert r.status_code == 200, r.text
            body = r.json()
            pills = body["pills"]
            assert len(pills) == 6, "FR-012 — exactly six named Pinnacle pills"
            titles = [p["title"] for p in pills]
            assert titles == [
                "Client 360",
                "Revenue Waterfall",
                "Advisor Productivity",
                "Client Profitability",
                "Trade Cost Attribution",
                "Budget vs. AUM Reality",
            ]
            # Every pill targets a fully-qualified iceberg table.
            for p in pills:
                assert p["target_iceberg_table"].startswith("iceberg.pinnacle_360.fct_")
                assert len(p["source_connection_ids"]) == 2

    asyncio.run(_run())


def test_pills_cache_short_circuits_second_call() -> None:
    async def _run() -> None:
        from httpx import ASGITransport, AsyncClient

        hdr = {"X-DSA-Session-ID": str(uuid4())}
        await _seed_two_connections(hdr)
        async with AsyncClient(
            transport=ASGITransport(app=_build_app()), base_url="http://t"
        ) as ac:
            first = (await ac.post("/workflow/pills", json={}, headers=hdr)).json()
            second = (await ac.post("/workflow/pills", json={}, headers=hdr)).json()
            # Same pill_ids — cache hit.
            assert [p["pill_id"] for p in first["pills"]] == [
                p["pill_id"] for p in second["pills"]
            ]
            assert second["generation_ms"] == 0  # cached path

    asyncio.run(_run())


def test_pills_force_regenerates() -> None:
    async def _run() -> None:
        from httpx import ASGITransport, AsyncClient

        hdr = {"X-DSA-Session-ID": str(uuid4())}
        await _seed_two_connections(hdr)
        async with AsyncClient(
            transport=ASGITransport(app=_build_app()), base_url="http://t"
        ) as ac:
            first = (await ac.post("/workflow/pills", json={}, headers=hdr)).json()
            second = (
                await ac.post(
                    "/workflow/pills", json={"force": True}, headers=hdr
                )
            ).json()
            assert [p["pill_id"] for p in first["pills"]] != [
                p["pill_id"] for p in second["pills"]
            ]

    asyncio.run(_run())


def test_draft_prd_returns_complete_prd() -> None:
    async def _run() -> None:
        from httpx import ASGITransport, AsyncClient

        hdr = {"X-DSA-Session-ID": str(uuid4())}
        await _seed_two_connections(hdr)
        async with AsyncClient(
            transport=ASGITransport(app=_build_app()), base_url="http://t"
        ) as ac:
            pills = (await ac.post("/workflow/pills", json={}, headers=hdr)).json()[
                "pills"
            ]
            client360 = next(p for p in pills if p["title"] == "Client 360")
            r = await ac.post(
                f"/workflow/pills/{client360['pill_id']}/draft-prd", headers=hdr
            )
            assert r.status_code == 200, r.text
            prd = r.json()
            assert prd["title"] == "Client 360"
            assert prd["target"]["table_name"] == "fct_client_360"
            assert len(prd["business_questions"]) >= 1
            assert len(prd["standards_applied"]) >= 1  # SC-011
            assert len(prd["source_pulls"]) >= 2  # cross-source
            assert prd["origin"] == "pill"
            assert prd["prd_id"]  # stamped

    asyncio.run(_run())


def test_draft_prd_404_for_unknown_pill() -> None:
    async def _run() -> None:
        from httpx import ASGITransport, AsyncClient

        hdr = {"X-DSA-Session-ID": str(uuid4())}
        await _seed_two_connections(hdr)
        async with AsyncClient(
            transport=ASGITransport(app=_build_app()), base_url="http://t"
        ) as ac:
            r = await ac.post(
                "/workflow/pills/not-a-real-pill-id/draft-prd", headers=hdr
            )
            assert r.status_code == 404

    asyncio.run(_run())


def test_non_pinnacle_dataset_falls_back_to_heuristic_pills(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SC-010: a non-Pinnacle dataset produces *its* pills, not Pinnacle's."""
    # Richer fixture: 6 schemas per source so the heuristic can legitimately
    # produce ≥6 pills without inventing filler.
    def fake_scan(conn, _ws):
        schemas = ["sales", "marketing", "inventory", "finance", "support", "logistics"]
        tables = []
        for schema in schemas:
            tables.append(
                {
                    "schema": schema,
                    "table_name": f"{schema}_facts",
                    "fully_qualified_name": f"shop.{schema}.{schema}_facts",
                    "columns": [
                        {"column_name": "id", "data_type": "int"},
                        {"column_name": "customer_id", "data_type": "int"},
                    ],
                    "primary_key": ["id"],
                    "foreign_keys": [],
                    "row_count": 100,
                }
            )
        return {
            "source_id": f"{conn.driver_type.value}_shop",
            "service": conn.driver_type.value,
            "database": "shop",
            "schemas": schemas,
            "tables": tables,
        }

    monkeypatch.setattr(
        "platform_agent.api.routes_workspace_discover._scan_connection",
        fake_scan,
    )

    async def _run() -> None:
        from httpx import ASGITransport, AsyncClient

        hdr = {"X-DSA-Session-ID": str(uuid4())}
        async with AsyncClient(
            transport=ASGITransport(app=_build_app()), base_url="http://t"
        ) as ac:
            await ac.post(
                "/workspace/connection",
                json={
                    "driver_type": "postgresql",
                    "display_name": "Shop PG #1",
                    "endpoint": "host1:5432",
                    "scope": "shop.public",
                    "credentials": {},
                },
                headers=hdr,
            )
            await ac.post(
                "/workspace/connection",
                json={
                    "driver_type": "redshift",
                    "display_name": "Shop RS",
                    "endpoint": "host2:5439",
                    "scope": "shop_archive.public",
                    "credentials": {},
                },
                headers=hdr,
            )
            await await_inflight()
            body = (
                await ac.post("/workflow/pills", json={"min_pills": 6}, headers=hdr)
            ).json()
            assert len(body["pills"]) >= 6
            # No Pinnacle named title in the heuristic output
            assert not any(p["title"] == "Client 360" for p in body["pills"])

    asyncio.run(_run())
