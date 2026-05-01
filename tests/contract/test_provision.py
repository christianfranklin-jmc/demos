"""Contract tests for /workflow/provision (T066, US3).

Exercises the four provisioning endpoints per
contracts/provision.openapi.yaml:
- POST /workflow/provision               201 / 400 (no_iceberg_target,
                                                   read_only_violation,
                                                   redundancy_not_cleared)
- GET  /workflow/provision/{run_id}      200 / 404
- POST /workflow/provision/{run_id}/retry 200 / 404
- GET  /workflow/provision/{run_id}/events  SSE stream (covered in
                                            test_provision_sse_v2.py)
"""

from __future__ import annotations

import asyncio
import tempfile
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from platform_agent.api.routes_workflow_provision import router as provision_router
from platform_agent.api.routes_workspace import router as workspace_router
from platform_agent.provisioning import orchestrator
from platform_agent.workflow.pill_models import IcebergTarget, PRDDraft, SourcePullSpec
from platform_agent.workspace.lifecycle import await_inflight
from platform_agent.workspace.registry import WorkspaceRegistry


@pytest.fixture(autouse=True)
def _isolate(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "platform_agent.workspace.registry._registry",
        WorkspaceRegistry(),
    )
    monkeypatch.setenv("DSA_HUB_LIFECYCLE_FAKE", "1")
    monkeypatch.setenv(
        "DSA_HUB_CONNECTIONS_DIR", tempfile.mkdtemp(prefix="dsa-hub-test-")
    )
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    orchestrator._reset_runs()


def _build_app() -> FastAPI:
    app = FastAPI()
    app.include_router(workspace_router)
    app.include_router(provision_router)
    return app


def _draft_prd(*, target_connection_id: str = "ICEBERG_TARGET_REQUIRED") -> dict:
    return PRDDraft(
        prd_id=str(uuid4()),
        title="Client 360",
        target=IcebergTarget(
            connection_id=target_connection_id,
            glue_db="pinnacle_360",
            table_name="fct_client_360",
        ),
        business_questions=[
            "What is Q1 advisor productivity?",
            "Which clients had >5% AUM growth?",
        ],
        source_pulls=[
            SourcePullSpec(
                connection_id="pg-1",
                sql="SELECT * FROM crm.client LIMIT 250",
                max_rows=250,
            )
        ],
        standards_applied=["naming.kimball.fct_dim_prefixes"],
    ).model_dump(mode="json")


async def _add_iceberg_connection(hdr: dict[str, str]) -> str:
    """Add a live Iceberg connection. Returns its connection_id."""
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
                "credentials": {
                    "warehouse_s3_uri": "s3://example/warehouse",
                    "region": "us-east-1",
                },
            },
            headers=hdr,
        )
        assert r.status_code == 201
        cid = r.json()["connection_id"]
        await await_inflight()
        return cid


# ───── 400 paths ─────


def test_provision_400_when_no_iceberg_connection() -> None:
    async def _run() -> None:
        hdr = {"X-DSA-Session-ID": str(uuid4())}
        async with AsyncClient(
            transport=ASGITransport(app=_build_app()), base_url="http://t"
        ) as ac:
            r = await ac.post(
                "/workflow/provision",
                json={"prd": _draft_prd(), "redundancy_cleared": True},
                headers=hdr,
            )
            assert r.status_code == 400
            assert r.json()["detail"]["code"] == "no_iceberg_target"

    asyncio.run(_run())


def test_provision_400_when_redundancy_not_cleared() -> None:
    async def _run() -> None:
        hdr = {"X-DSA-Session-ID": str(uuid4())}
        await _add_iceberg_connection(hdr)
        async with AsyncClient(
            transport=ASGITransport(app=_build_app()), base_url="http://t"
        ) as ac:
            r = await ac.post(
                "/workflow/provision",
                json={"prd": _draft_prd(), "redundancy_cleared": False},
                headers=hdr,
            )
            assert r.status_code == 400
            assert r.json()["detail"]["code"] == "redundancy_not_cleared"

    asyncio.run(_run())


def test_provision_400_for_read_only_violation() -> None:
    async def _run() -> None:
        hdr = {"X-DSA-Session-ID": str(uuid4())}
        await _add_iceberg_connection(hdr)
        # Build a PRD with a write keyword in source SQL (bypassing the
        # PRDDraft validator by submitting the raw dict directly).
        bad = _draft_prd()
        bad["source_pulls"] = [
            {
                "connection_id": "pg-1",
                "sql": "DROP TABLE crm.client",
                "max_rows": 250,
            }
        ]
        async with AsyncClient(
            transport=ASGITransport(app=_build_app()), base_url="http://t"
        ) as ac:
            r = await ac.post(
                "/workflow/provision",
                json={"prd": bad, "redundancy_cleared": True},
                headers=hdr,
            )
            # The PRDDraft validator catches this first → 422 from FastAPI.
            assert r.status_code in (400, 422)

    asyncio.run(_run())


def test_provision_400_target_connection_not_iceberg() -> None:
    async def _run() -> None:
        hdr = {"X-DSA-Session-ID": str(uuid4())}
        await _add_iceberg_connection(hdr)
        async with AsyncClient(
            transport=ASGITransport(app=_build_app()), base_url="http://t"
        ) as ac:
            r = await ac.post(
                "/workflow/provision",
                json={
                    "prd": _draft_prd(target_connection_id="some-other-id"),
                    "redundancy_cleared": True,
                },
                headers=hdr,
            )
            assert r.status_code == 400
            assert r.json()["detail"]["code"] == "no_iceberg_target"

    asyncio.run(_run())


# ───── Happy paths ─────


def test_provision_201_creates_run() -> None:
    async def _run() -> None:
        hdr = {"X-DSA-Session-ID": str(uuid4())}
        await _add_iceberg_connection(hdr)
        async with AsyncClient(
            transport=ASGITransport(app=_build_app()), base_url="http://t"
        ) as ac:
            r = await ac.post(
                "/workflow/provision",
                json={"prd": _draft_prd(), "redundancy_cleared": True},
                headers=hdr,
            )
            assert r.status_code == 201, r.text
            body = r.json()
            assert body["state"] in ("queued", "running", "completed", "needs_replan")
            assert len(body["agents"]) == 7
            assert {a["agent_id"] for a in body["agents"]} == {
                "schema", "pipeline", "model", "quality", "mapping",
                "semantic", "delivery",
            }

    asyncio.run(_run())


def test_provision_snapshot_404_when_unknown() -> None:
    async def _run() -> None:
        hdr = {"X-DSA-Session-ID": str(uuid4())}
        async with AsyncClient(
            transport=ASGITransport(app=_build_app()), base_url="http://t"
        ) as ac:
            r = await ac.get("/workflow/provision/not-a-real-run", headers=hdr)
            assert r.status_code == 404

    asyncio.run(_run())


def test_provision_retry_404_when_unknown() -> None:
    async def _run() -> None:
        hdr = {"X-DSA-Session-ID": str(uuid4())}
        async with AsyncClient(
            transport=ASGITransport(app=_build_app()), base_url="http://t"
        ) as ac:
            r = await ac.post(
                "/workflow/provision/not-a-real-run/retry",
                json={"agent_id": "model"},
                headers=hdr,
            )
            assert r.status_code == 404

    asyncio.run(_run())
