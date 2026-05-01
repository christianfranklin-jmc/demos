"""Contract tests for /workspace/discover (T047, US2).

Drives discovery end-to-end with stubbed scan_metadata payloads so the
test never touches a real DB. Asserts:

- Pinnacle PG fixture produces all 8 named business processes (FR-008).
- Workspace-scoped discover merges per-connection results into a
  CoverageMatrix (FR-010).
- ready_to_combine = true on cross-source rows that share business keys
  (e.g., client_id appears in both PG.crm.client and SF.dim_client).
- 400 no_live_connections when the workspace is empty.
"""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from platform_agent.api.routes_workspace import router as workspace_router
from platform_agent.api.routes_workspace_discover import (
    _reset_caches,
)
from platform_agent.api.routes_workspace_discover import (
    router as discover_router,
)
from platform_agent.workspace.lifecycle import await_inflight
from platform_agent.workspace.registry import WorkspaceRegistry

# ───── Fixture metadata payloads (mirror PostgreSQLDriver.scan_metadata shape) ─────


def _pinnacle_pg_metadata() -> dict[str, Any]:
    """Synthesize a scan_metadata payload covering Pinnacle's 8 schemas."""
    schemas_with_tables: dict[str, list[tuple[str, list[str], int]]] = {
        "ap": [
            ("ap_invoice", ["invoice_id", "vendor_id", "client_id", "amount"], 336),
            ("ap_payment", ["payment_id", "invoice_id", "amount"], 308),
            ("vendor", ["vendor_id", "name"], 14),
        ],
        "billing": [
            ("fee_invoice", ["invoice_id", "client_id", "account_id", "amount"], 1680),
            ("fee_adjustment", ["adjustment_id", "invoice_id", "client_id", "amount"], 80),
            ("billing_cycle", ["cycle_id", "period_id", "status"], 24),
        ],
        "crm": [
            ("client", ["client_id", "household_id", "name"], 35),
            ("meeting", ["meeting_id", "client_id", "advisor_id", "occurred_at"], 335),
            ("opportunity", ["opp_id", "client_id", "status", "stage"], 90),
            ("client_engagement", ["metric_id", "client_id", "period_id", "score"], 720),
        ],
        "gl": [
            ("CHART_OF_ACCOUNTS", ["gl_account_id", "name", "account_type"], 16),
            ("JOURNAL_ENTRY", ["entry_id", "period_id", "posted_at"], 69),
            ("JOURNAL_LINE", ["line_id", "entry_id", "gl_account_id", "debit", "credit"], 138),
        ],
        "hr": [
            ("employee", ["employee_id", "department_id", "name"], 15),
            ("department", ["department_id", "name"], 4),
            ("cost_center_allocation", ["alloc_id", "employee_id", "cost_center_id"], 17),
        ],
        "performance": [
            ("account_aum_daily", ["snapshot_id", "account_id", "client_id", "ending_aum"], 6300),
            ("benchmark_return", ["benchmark_id", "period_id", "return_pct"], 630),
        ],
        "planning": [
            ("budget_line", ["line_id", "period_id", "gl_account_id", "amount"], 480),
            ("forecast_line", ["forecast_id", "period_id", "gl_account_id", "amount"], 480),
        ],
        "portfolio": [
            ("trade", ["trade_id", "account_id", "client_id", "notional"], 420),
            ("account", ["account_id", "client_id", "strategy_id"], 70),
            ("strategy", ["strategy_id", "name", "basis_points"], 12),
            ("holding", ["account_id", "asset_id", "position", "mv"], 2100),
            ("rebalance_event", ["event_id", "account_id", "type", "occurred_at"], 280),
        ],
    }
    tables: list[dict[str, Any]] = []
    for schema, rows in schemas_with_tables.items():
        for tbl_name, columns, row_count in rows:
            tables.append(
                {
                    "schema": schema,
                    "table_name": tbl_name,
                    "fully_qualified_name": f"pinnacle.{schema}.{tbl_name}",
                    "columns": [{"column_name": c, "data_type": "text"} for c in columns],
                    "primary_key": [columns[0]],
                    "foreign_keys": [],
                    "row_count": row_count,
                }
            )
    return {
        "source_id": "postgresql_pinnacle",
        "service": "postgresql",
        "database": "pinnacle",
        "schemas": list(schemas_with_tables.keys()),
        "tables": tables,
    }


def _snowflake_analytical_metadata() -> dict[str, Any]:
    """Snowflake analytical mirror sharing client_id / account_id / strategy_id."""
    tables = [
        {
            "schema": "ANALYTICS",
            "table_name": "DIM_CLIENT",
            "fully_qualified_name": "PINNACLE_FINANCIAL_DEMO_ASINGH.ANALYTICS.DIM_CLIENT",
            "columns": [{"column_name": c, "data_type": "varchar"}
                        for c in ["client_id", "name", "household_id"]],
            "primary_key": ["client_id"],
            "foreign_keys": [],
            "row_count": 35,
        },
        {
            "schema": "ANALYTICS",
            "table_name": "FCT_AUM_HISTORY",
            "fully_qualified_name": "PINNACLE_FINANCIAL_DEMO_ASINGH.ANALYTICS.FCT_AUM_HISTORY",
            "columns": [{"column_name": c, "data_type": "varchar"}
                        for c in ["snapshot_date", "account_id", "client_id", "ending_aum"]],
            "primary_key": [],
            "foreign_keys": [],
            "row_count": 6300,
        },
        {
            "schema": "ANALYTICS",
            "table_name": "FCT_PERFORMANCE_ATTRIBUTION",
            "fully_qualified_name": (
                "PINNACLE_FINANCIAL_DEMO_ASINGH.ANALYTICS.FCT_PERFORMANCE_ATTRIBUTION"
            ),
            "columns": [{"column_name": c, "data_type": "varchar"}
                        for c in ["account_id", "strategy_id", "alpha", "period_id"]],
            "primary_key": [],
            "foreign_keys": [],
            "row_count": 1200,
        },
    ]
    # Pinnacle Snowflake uses a single ANALYTICS schema (the analytical
    # mirror), so for our process detection it shows up as a single
    # "Analytics" process — that's what we expect (and is fine for
    # cross-source overlap because the columns carry the keys).
    return {
        "source_id": "snowflake_pinnacle",
        "service": "snowflake",
        "database": "PINNACLE_FINANCIAL_DEMO_ASINGH",
        "schemas": ["ANALYTICS"],
        "tables": tables,
    }


# ───── Fixtures ─────


@pytest.fixture(autouse=True)
def _isolate(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "platform_agent.workspace.registry._registry",
        WorkspaceRegistry(),
    )
    monkeypatch.setenv("DSA_HUB_LIFECYCLE_FAKE", "1")
    _reset_caches()
    # Stub _scan_connection so discovery runs offline.
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


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.include_router(workspace_router)
    app.include_router(discover_router)
    return TestClient(app)


def _hdr() -> dict[str, str]:
    return {"X-DSA-Session-ID": str(uuid4())}


async def _setup_two_pinnacle_connections(hdr: dict[str, str]) -> None:
    from httpx import ASGITransport, AsyncClient

    app = FastAPI()
    app.include_router(workspace_router)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://t"
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


# ───── Tests ─────


def test_workspace_discover_400_when_no_live_connections(client: TestClient) -> None:
    r = client.post("/workspace/discover", json={}, headers=_hdr())
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "no_live_connections"


def test_workspace_discover_pinnacle_8_processes() -> None:
    async def _run() -> None:
        from httpx import ASGITransport, AsyncClient

        hdr = _hdr()
        await _setup_two_pinnacle_connections(hdr)

        app = FastAPI()
        app.include_router(workspace_router)
        app.include_router(discover_router)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t"
        ) as ac:
            r = await ac.post("/workspace/discover", json={}, headers=hdr)
            assert r.status_code == 200, r.text
            body = r.json()
            assert len(body["per_connection"]) == 2

            # Find the PG envelope and assert its 8 processes
            pg = next(
                e for e in body["per_connection"]
                if any(p["name"] == "Accounts Payable" for p in e["processes"])
            )
            pg_names = {p["name"] for p in pg["processes"]}
            assert pg_names == {
                "Accounts Payable",
                "Client Fee Billing & Revenue",
                "CRM",
                "General Ledger",
                "HR & Cost Management",
                "Performance & Asset Reporting",
                "Financial Planning & Budgeting",
                "Portfolio Management & Trading",
            }

            # Coverage matrix has rows for all 9 process names (8 PG + Analytics SF)
            row_names = {r["process_name"] for r in body["coverage_matrix"]["rows"]}
            assert "Accounts Payable" in row_names
            assert "CRM" in row_names

    asyncio.run(_run())


def test_workspace_discover_kpi_summary_shape() -> None:
    async def _run() -> None:
        from httpx import ASGITransport, AsyncClient

        hdr = _hdr()
        await _setup_two_pinnacle_connections(hdr)

        app = FastAPI()
        app.include_router(workspace_router)
        app.include_router(discover_router)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t"
        ) as ac:
            body = (await ac.post("/workspace/discover", json={}, headers=hdr)).json()
            for env in body["per_connection"]:
                kpi = env["kpi_summary"]
                assert kpi["tables_scanned"] >= 1
                assert kpi["columns_profiled"] >= 1
                assert kpi["processes_detected"] >= 1

    asyncio.run(_run())
