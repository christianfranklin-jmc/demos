"""Contract tests for /workflow/redundancy-check (T112, US6).

Asserts:
- 400 no_iceberg_target when the PRD target connection isn't a live Iceberg
  connection in the workspace.
- net_new state when the target store is empty.
- partial_overlap state when an entity name matches; cleared_to_provision
  remains false until decisions are recorded.
- duplicate state when every proposed entity matches with high overlap;
  decide() requires override_rationale to clear.
- /decide records decisions and flips cleared_to_provision.
"""

from __future__ import annotations

import asyncio
import tempfile
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from platform_agent.api.routes_redundancy import (
    _reset_reports,
)
from platform_agent.api.routes_redundancy import (
    router as redundancy_router,
)
from platform_agent.api.routes_workspace import router as workspace_router
from platform_agent.semantic.models import (
    Attribute,
    Domain,
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
    _reset_reports()


def _build_app() -> FastAPI:
    app = FastAPI()
    app.include_router(workspace_router)
    app.include_router(redundancy_router)
    return app


async def _add_iceberg_connection(hdr: dict[str, str]) -> str:
    async with AsyncClient(
        transport=ASGITransport(app=_build_app()), base_url="http://t"
    ) as ac:
        r = await ac.post(
            "/workspace/connection",
            json={
                "driver_type": "iceberg",
                "display_name": "Iceberg Target",
                "endpoint": "glue://us-east-1/pinnacle_360",
                "scope": "pinnacle_360",
                "credentials": {"warehouse_s3_uri": "s3://x/y", "region": "us-east-1"},
            },
            headers=hdr,
        )
        await await_inflight()
        return r.json()["connection_id"]


def _seed_existing_client_entity(connection_id: str) -> None:
    """Add an existing 'client' entity in the target store."""
    now = datetime.now(tz=UTC)
    store = make_store(connection_id)
    store.upsert_entity(
        SemanticEntity(
            entity_id="e-existing-client",
            connection_id=connection_id,
            name="client",
            domain=Domain.CRM,
            attributes=[
                Attribute(name="client_id", data_type="int"),
                Attribute(name="name", data_type="varchar"),
                Attribute(name="household_id", data_type="int"),
            ],
            physical_binding_ids=["b-existing"],
            created_at=now,
            updated_at=now,
        )
    )
    store.upsert_binding(
        PhysicalBinding(
            binding_id="b-existing",
            entity_id="e-existing-client",
            connection_id=connection_id,
            fully_qualified_name="iceberg.pinnacle_360.dim_client",
            column_map={"client_id": "client_id"},
        )
    )
    store.upsert_metric(
        Metric(
            metric_id="m-existing-count",
            connection_id=connection_id,
            name="active_clients",
            definition_sql="SELECT COUNT(*) FROM dim_client",
            entity_ids=["e-existing-client"],
        )
    )
    store.close()


def _prd(target_id: str, *, entity_name: str = "client") -> dict:
    return {
        "prd_id": str(uuid4()),
        "title": "Client 360",
        "target": {
            "connection_id": target_id,
            "glue_db": "pinnacle_360",
            "table_name": "fct_client_360",
        },
        "entities_proposed": [
            {
                "name": entity_name,
                "attributes": [
                    {"name": "client_id", "data_type": "int", "is_pii": False},
                    {"name": "name", "data_type": "varchar", "is_pii": False},
                ],
            }
        ],
        "metrics_proposed": [],
        "joins_identified": [],
        "business_questions": ["q1"],
        "source_pulls": [
            {
                "connection_id": "pg-1",
                "sql": "SELECT * FROM crm.client LIMIT 250",
                "max_rows": 250,
            }
        ],
        "standards_applied": ["s"],
        "origin": "pill",
    }


def test_400_when_target_not_live_iceberg() -> None:
    async def _run() -> None:
        hdr = {"X-DSA-Session-ID": str(uuid4())}
        async with AsyncClient(
            transport=ASGITransport(app=_build_app()), base_url="http://t"
        ) as ac:
            r = await ac.post(
                "/workflow/redundancy-check",
                json={"prd": _prd("ICEBERG_TARGET_REQUIRED")},
                headers=hdr,
            )
            assert r.status_code == 400
            assert r.json()["detail"]["code"] == "no_iceberg_target"

    asyncio.run(_run())


def test_net_new_when_target_store_is_empty() -> None:
    async def _run() -> None:
        hdr = {"X-DSA-Session-ID": str(uuid4())}
        cid = await _add_iceberg_connection(hdr)
        async with AsyncClient(
            transport=ASGITransport(app=_build_app()), base_url="http://t"
        ) as ac:
            r = await ac.post(
                "/workflow/redundancy-check",
                json={"prd": _prd(cid)},
                headers=hdr,
            )
            assert r.status_code == 200
            body = r.json()
            assert body["state"] == "net_new"
            assert body["overlaps"] == []
            assert body["cleared_to_provision"] is True

    asyncio.run(_run())


def test_partial_overlap_blocks_until_decisions_recorded() -> None:
    async def _run() -> None:
        hdr = {"X-DSA-Session-ID": str(uuid4())}
        cid = await _add_iceberg_connection(hdr)
        _seed_existing_client_entity(cid)
        # PRD proposes a `client` entity but with attrs that overlap only
        # partially with the seeded one: client_id (match) + email (new) +
        # engagement_score (new). 1/3 → 33% overlap → partial_overlap.
        prd = _prd(cid, entity_name="client")
        prd["entities_proposed"][0]["attributes"] = [
            {"name": "client_id", "data_type": "int", "is_pii": False},
            {"name": "email", "data_type": "varchar", "is_pii": True},
            {"name": "engagement_score", "data_type": "double", "is_pii": False},
        ]
        async with AsyncClient(
            transport=ASGITransport(app=_build_app()), base_url="http://t"
        ) as ac:
            r = await ac.post(
                "/workflow/redundancy-check",
                json={"prd": prd},
                headers=hdr,
            )
            assert r.status_code == 200
            body = r.json()
            assert body["state"] == "partial_overlap", body
            assert len(body["overlaps"]) == 1
            assert body["overlaps"][0]["existing_id"] == "e-existing-client"
            # not cleared yet — decisions are pending
            assert body["cleared_to_provision"] is False

            # decide → reuse the existing entity
            d = await ac.post(
                f"/workflow/redundancy-check/{body['report_id']}/decide",
                json={
                    "decisions": [
                        {
                            "overlap_existing_id": "e-existing-client",
                            "kind": "reuse",
                            "rationale": "",
                        }
                    ]
                },
                headers=hdr,
            )
            assert d.status_code == 200
            assert d.json()["cleared_to_provision"] is True
            assert d.json()["pending_overlaps"] == 0

    asyncio.run(_run())


def test_duplicate_requires_override_rationale_to_clear() -> None:
    async def _run() -> None:
        hdr = {"X-DSA-Session-ID": str(uuid4())}
        cid = await _add_iceberg_connection(hdr)
        _seed_existing_client_entity(cid)
        # PRD with a single proposed entity that fully overlaps existing.
        prd = _prd(cid, entity_name="client")
        prd["entities_proposed"][0]["attributes"] = [
            {"name": "client_id", "data_type": "int", "is_pii": False},
            {"name": "name", "data_type": "varchar", "is_pii": False},
            {"name": "household_id", "data_type": "int", "is_pii": False},
        ]
        async with AsyncClient(
            transport=ASGITransport(app=_build_app()), base_url="http://t"
        ) as ac:
            r = await ac.post(
                "/workflow/redundancy-check", json={"prd": prd}, headers=hdr
            )
            body = r.json()
            assert body["state"] == "duplicate"

            # decide WITHOUT override_rationale → still blocked
            d = await ac.post(
                f"/workflow/redundancy-check/{body['report_id']}/decide",
                json={
                    "decisions": [
                        {
                            "overlap_existing_id": "e-existing-client",
                            "kind": "override",
                            "rationale": "",
                        }
                    ]
                },
                headers=hdr,
            )
            assert d.json()["cleared_to_provision"] is False

            # decide WITH override_rationale → cleared
            d2 = await ac.post(
                f"/workflow/redundancy-check/{body['report_id']}/decide",
                json={
                    "decisions": [
                        {
                            "overlap_existing_id": "e-existing-client",
                            "kind": "override",
                            "rationale": "regulatory schema rewrite",
                        }
                    ],
                    "override_rationale": "regulatory schema rewrite",
                },
                headers=hdr,
            )
            assert d2.json()["cleared_to_provision"] is True

    asyncio.run(_run())


def test_decide_404_for_unknown_report() -> None:
    async def _run() -> None:
        hdr = {"X-DSA-Session-ID": str(uuid4())}
        async with AsyncClient(
            transport=ASGITransport(app=_build_app()), base_url="http://t"
        ) as ac:
            r = await ac.post(
                "/workflow/redundancy-check/no-such-report/decide",
                json={"decisions": []},
                headers=hdr,
            )
            assert r.status_code == 404

    asyncio.run(_run())
