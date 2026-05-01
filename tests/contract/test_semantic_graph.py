"""Contract tests for /semantic/graph (T103, US5).

Asserts:
- Empty store returns empty entity/join lists with zero KPIs.
- Populated store (entity + binding + metric + join) returns the
  expected counts + KPI strip.
- Domain filter applies.
- 404 when the connection_id is not in the workspace.
- Entity detail endpoint returns entity + bindings + metrics.
"""

from __future__ import annotations

import asyncio
import tempfile
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from platform_agent.api.routes_semantic import router as semantic_router
from platform_agent.api.routes_workspace import router as workspace_router
from platform_agent.semantic.models import (
    Attribute,
    Cardinality,
    Domain,
    Join,
    Metric,
    PhysicalBinding,
    SemanticEntity,
)
from platform_agent.semantic.store import make_store
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
        "platform_agent.workspace.registry._registry", WorkspaceRegistry()
    )


def _build_app() -> FastAPI:
    app = FastAPI()
    app.include_router(workspace_router)
    app.include_router(semantic_router)
    return app


async def _add_pg_connection(hdr: dict[str, str]) -> str:
    async with AsyncClient(
        transport=ASGITransport(app=_build_app()), base_url="http://t"
    ) as ac:
        r = await ac.post(
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
        return r.json()["connection_id"]


def _seed_store(connection_id: str) -> tuple[str, str]:
    """Populate the store with an entity + binding + metric + a self-join."""
    now = datetime.now(tz=UTC)
    store = make_store(connection_id)
    e1 = SemanticEntity(
        entity_id="e1",
        connection_id=connection_id,
        name="client",
        domain=Domain.CRM,
        attributes=[Attribute(name="client_id", data_type="int")],
        physical_binding_ids=["b1"],
        created_at=now,
        updated_at=now,
    )
    e2 = SemanticEntity(
        entity_id="e2",
        connection_id=connection_id,
        name="account",
        domain=Domain.WEALTH_MGMT,
        attributes=[Attribute(name="account_id", data_type="int")],
        physical_binding_ids=["b2"],
        created_at=now,
        updated_at=now,
    )
    store.upsert_entity(e1)
    store.upsert_entity(e2)
    store.upsert_binding(
        PhysicalBinding(
            binding_id="b1",
            entity_id="e1",
            connection_id=connection_id,
            fully_qualified_name="pinnacle.crm.client",
            column_map={"client_id": "client_id"},
        )
    )
    store.upsert_binding(
        PhysicalBinding(
            binding_id="b2",
            entity_id="e2",
            connection_id=connection_id,
            fully_qualified_name="pinnacle.portfolio.account",
            column_map={"account_id": "account_id"},
        )
    )
    store.upsert_metric(
        Metric(
            metric_id="m1",
            connection_id=connection_id,
            name="active_clients",
            definition_sql="SELECT COUNT(*) FROM pinnacle.crm.client",
            entity_ids=["e1"],
        )
    )
    store.upsert_join(
        Join(
            join_id="j1",
            connection_id=connection_id,
            left_entity_id="e1",
            right_entity_id="e2",
            join_keys=[("client_id", "client_id")],
            cardinality=Cardinality.ONE_TO_MANY,
        )
    )
    store.close()
    return e1.entity_id, e2.entity_id


def test_graph_404_when_connection_not_in_workspace() -> None:
    async def _run() -> None:
        hdr = {"X-DSA-Session-ID": str(uuid4())}
        async with AsyncClient(
            transport=ASGITransport(app=_build_app()), base_url="http://t"
        ) as ac:
            r = await ac.get(
                "/semantic/graph?connection_id=not-a-real-connection",
                headers=hdr,
            )
            assert r.status_code == 404

    asyncio.run(_run())


def test_graph_empty_store_returns_zero_counts() -> None:
    async def _run() -> None:
        hdr = {"X-DSA-Session-ID": str(uuid4())}
        cid = await _add_pg_connection(hdr)
        async with AsyncClient(
            transport=ASGITransport(app=_build_app()), base_url="http://t"
        ) as ac:
            r = await ac.get(f"/semantic/graph?connection_id={cid}", headers=hdr)
            assert r.status_code == 200, r.text
            body = r.json()
            assert body["entities"] == []
            assert body["joins"] == []
            assert body["kpi_strip"] == {
                "entities": 0,
                "metrics": 0,
                "joins": 0,
                "bindings": 0,
                "processes_mapped_pct": 0.0,
            }

    asyncio.run(_run())


def test_graph_returns_entities_joins_and_kpis() -> None:
    async def _run() -> None:
        hdr = {"X-DSA-Session-ID": str(uuid4())}
        cid = await _add_pg_connection(hdr)
        _seed_store(cid)
        async with AsyncClient(
            transport=ASGITransport(app=_build_app()), base_url="http://t"
        ) as ac:
            r = await ac.get(f"/semantic/graph?connection_id={cid}", headers=hdr)
            assert r.status_code == 200, r.text
            body = r.json()
            assert {e["name"] for e in body["entities"]} == {"client", "account"}
            assert body["kpi_strip"]["entities"] == 2
            assert body["kpi_strip"]["metrics"] == 1
            assert body["kpi_strip"]["joins"] == 1
            assert body["kpi_strip"]["bindings"] == 2
            # client has 1 metric + 1 binding; account has 0 + 1.
            client_row = next(e for e in body["entities"] if e["name"] == "client")
            account_row = next(
                e for e in body["entities"] if e["name"] == "account"
            )
            assert client_row["metric_count"] == 1
            assert client_row["binding_count"] == 1
            assert account_row["metric_count"] == 0

    asyncio.run(_run())


def test_graph_domain_filter_applies() -> None:
    async def _run() -> None:
        hdr = {"X-DSA-Session-ID": str(uuid4())}
        cid = await _add_pg_connection(hdr)
        _seed_store(cid)
        async with AsyncClient(
            transport=ASGITransport(app=_build_app()), base_url="http://t"
        ) as ac:
            r = await ac.get(
                f"/semantic/graph?connection_id={cid}&domain=crm", headers=hdr
            )
            body = r.json()
            assert {e["name"] for e in body["entities"]} == {"client"}

    asyncio.run(_run())


def test_entity_detail_returns_bindings_and_metrics() -> None:
    async def _run() -> None:
        hdr = {"X-DSA-Session-ID": str(uuid4())}
        cid = await _add_pg_connection(hdr)
        _seed_store(cid)
        async with AsyncClient(
            transport=ASGITransport(app=_build_app()), base_url="http://t"
        ) as ac:
            r = await ac.get(
                f"/semantic/entities/e1?connection_id={cid}", headers=hdr
            )
            assert r.status_code == 200, r.text
            body = r.json()
            assert body["entity"]["name"] == "client"
            assert len(body["bindings"]) == 1
            assert body["bindings"][0]["fully_qualified_name"] == (
                "pinnacle.crm.client"
            )
            assert len(body["metrics"]) == 1
            assert body["metrics"][0]["name"] == "active_clients"

    asyncio.run(_run())


def test_entity_detail_404_when_unknown() -> None:
    async def _run() -> None:
        hdr = {"X-DSA-Session-ID": str(uuid4())}
        cid = await _add_pg_connection(hdr)
        async with AsyncClient(
            transport=ASGITransport(app=_build_app()), base_url="http://t"
        ) as ac:
            r = await ac.get(
                f"/semantic/entities/no-such-entity?connection_id={cid}",
                headers=hdr,
            )
            assert r.status_code == 404

    asyncio.run(_run())
