"""SC-011: every generated PRD ends with a non-empty Standards-applied footer.

Asserts both surfaces:
- The /standards endpoints expose all 6 categories (FR-037).
- Every PillSuggestion produced by `pill_generator` carries a non-empty
  `seed_prd_body.standards_applied` (FR-038, SC-011).
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from uuid import uuid4

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from platform_agent.api.routes_standards import CATEGORIES
from platform_agent.api.routes_standards import router as standards_router
from platform_agent.semantic.models import Domain
from platform_agent.tools.pill_generator import generate_pills
from platform_agent.workflow.discovery_models import BusinessProcess, VolumeSignal
from platform_agent.workspace.models import (
    Connection,
    ConnectionKPIs,
    ConnectionStatus,
    DriverType,
)


def _build_app() -> FastAPI:
    app = FastAPI()
    app.include_router(standards_router)
    return app


def test_standards_lists_all_six_categories() -> None:
    async def _run() -> None:
        hdr = {"X-DSA-Session-ID": str(uuid4())}
        async with AsyncClient(
            transport=ASGITransport(app=_build_app()), base_url="http://t"
        ) as ac:
            r = await ac.get("/standards", headers=hdr)
            assert r.status_code == 200, r.text
            body = r.json()
            keys = [c["key"] for c in body["categories"]]
            assert keys == [k for k, _ in CATEGORIES]
            assert len(keys) == 6  # FR-037
            for cat in body["categories"]:
                assert cat["preview"]  # non-empty preview text

    asyncio.run(_run())


def test_standards_category_returns_markdown_body() -> None:
    async def _run() -> None:
        hdr = {"X-DSA-Session-ID": str(uuid4())}
        async with AsyncClient(
            transport=ASGITransport(app=_build_app()), base_url="http://t"
        ) as ac:
            r = await ac.get("/standards/naming", headers=hdr)
            assert r.status_code == 200, r.text
            body = r.json()
            assert body["key"] == "naming"
            assert "Kimball" in body["body"] or "Naming" in body["body"]

    asyncio.run(_run())


def test_standards_404_for_unknown_category() -> None:
    async def _run() -> None:
        hdr = {"X-DSA-Session-ID": str(uuid4())}
        async with AsyncClient(
            transport=ASGITransport(app=_build_app()), base_url="http://t"
        ) as ac:
            r = await ac.get("/standards/not-a-real-category", headers=hdr)
            assert r.status_code == 404

    asyncio.run(_run())


def _conn(driver: DriverType, scope: str) -> Connection:
    return Connection(
        connection_id=f"conn-{driver.value}",
        driver_type=driver,
        display_name=f"{driver.value} test",
        endpoint="x",
        scope=scope,
        status=ConnectionStatus.LIVE,
        kpis=ConnectionKPIs(),
        added_at=datetime.now(tz=UTC),
    )


def _process(connection_id: str, name: str, domain: Domain) -> BusinessProcess:
    return BusinessProcess(
        process_id=str(uuid4()),
        connection_id=connection_id,
        name=name,
        domain=domain,
        volume_signal=VolumeSignal(row_count=0),
        last_activity_ts=datetime.now(tz=UTC),
        sparkline=[0.0] * 12,
        backing_tables=[],
    )


def test_every_pill_carries_non_empty_standards_applied_footer() -> None:
    """SC-011 — every generated PRD ends with a non-empty Standards footer."""
    pg_conn = _conn(DriverType.POSTGRESQL, "pinnacle.public")
    sf_conn = _conn(DriverType.SNOWFLAKE, "PINNACLE_FINANCIAL_DEMO_ASINGH.ANALYTICS")
    # Pinnacle path requires ≥6 of 8 named processes.
    pinnacle_processes = [
        _process(pg_conn.connection_id, name, Domain.UNSPECIFIED)
        for name in [
            "Accounts Payable",
            "Client Fee Billing & Revenue",
            "CRM",
            "General Ledger",
            "HR & Cost Management",
            "Performance & Asset Reporting",
            "Financial Planning & Budgeting",
            "Portfolio Management & Trading",
        ]
    ]
    sf_processes = [_process(sf_conn.connection_id, "Analytics", Domain.UNSPECIFIED)]
    pills = generate_pills(
        per_connection=[(pg_conn, pinnacle_processes), (sf_conn, sf_processes)],
        min_pills=6,
    )
    assert len(pills) == 6
    for pill in pills:
        assert pill.seed_prd_body.standards_applied  # non-empty
        assert all(s for s in pill.seed_prd_body.standards_applied)  # no empty strings
