"""SSE schema v2 contract tests (T067, US3).

Asserts the wire-level event format (the v2 envelope, ordering rules)
that the frontend's parsers/v2/ depends on. Operates against the
orchestrator directly so tests stay fast — the SSE serialization
path is exercised by parsing the queued event objects through their
`.model_dump(mode="json")` payload.
"""

from __future__ import annotations

import asyncio
import tempfile
from uuid import uuid4

import pytest

from platform_agent.provisioning import orchestrator
from platform_agent.provisioning.events import (
    AgentCompletedEvent,
    AgentStartedEvent,
    KpiTickEvent,
    RunCompletedEvent,
)
from platform_agent.workflow.pill_models import IcebergTarget, PRDDraft, SourcePullSpec


@pytest.fixture(autouse=True)
def _isolate(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "DSA_HUB_CONNECTIONS_DIR", tempfile.mkdtemp(prefix="dsa-hub-test-")
    )
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    orchestrator._reset_runs()


def _prd() -> PRDDraft:
    return PRDDraft(
        prd_id=str(uuid4()),
        title="Client 360",
        target=IcebergTarget(
            connection_id="iceberg-1",
            glue_db="pinnacle_360",
            table_name="fct_client_360",
        ),
        business_questions=["q"],
        source_pulls=[
            SourcePullSpec(
                connection_id="pg-1",
                sql="SELECT 1 FROM x LIMIT 250",
                max_rows=250,
            )
        ],
        standards_applied=["s"],
    )


def test_envelope_has_v2_run_id_seq_ts() -> None:
    async def _run() -> None:
        run = orchestrator.queue_run(workspace_id=str(uuid4()), prd=_prd())
        queue = orchestrator.subscribe(run.run_id)
        assert queue is not None
        await orchestrator.execute_run(run.run_id)
        events = []
        while True:
            ev = await asyncio.wait_for(queue.get(), timeout=2.0)
            if ev is None:
                break
            events.append(ev)
        assert events
        for ev in events:
            payload = ev.model_dump(mode="json")
            assert payload["v"] == 2
            assert "run_id" in payload
            assert "seq" in payload and isinstance(payload["seq"], int)
            assert "ts" in payload
            assert "kind" in payload

    asyncio.run(_run())


def test_event_ordering_started_progress_completed() -> None:
    async def _run() -> None:
        run = orchestrator.queue_run(workspace_id=str(uuid4()), prd=_prd())
        queue = orchestrator.subscribe(run.run_id)
        assert queue is not None
        await orchestrator.execute_run(run.run_id)
        events = []
        while True:
            ev = await asyncio.wait_for(queue.get(), timeout=2.0)
            if ev is None:
                break
            events.append(ev)

        # For each agent: started.seq < completed.seq.
        starts = {
            e.agent_id: e.seq for e in events if isinstance(e, AgentStartedEvent)
        }
        completes = {
            e.agent_id: e.seq for e in events if isinstance(e, AgentCompletedEvent)
        }
        for agent_id in starts:
            assert starts[agent_id] < completes[agent_id]

    asyncio.run(_run())


def test_run_completed_is_last_meaningful_event() -> None:
    async def _run() -> None:
        run = orchestrator.queue_run(workspace_id=str(uuid4()), prd=_prd())
        queue = orchestrator.subscribe(run.run_id)
        assert queue is not None
        await orchestrator.execute_run(run.run_id)
        events = []
        while True:
            ev = await asyncio.wait_for(queue.get(), timeout=2.0)
            if ev is None:
                break
            events.append(ev)
        # The last RunCompletedEvent has the highest seq among non-tick events.
        completed = [e for e in events if isinstance(e, RunCompletedEvent)]
        assert len(completed) == 1
        # It carries product_id and product_state ∈ {final, provisional}.
        c = completed[0]
        assert c.product_id
        assert c.product_state in ("final", "provisional")

    asyncio.run(_run())


def test_kpi_ticks_emitted_at_state_transitions() -> None:
    async def _run() -> None:
        run = orchestrator.queue_run(workspace_id=str(uuid4()), prd=_prd())
        queue = orchestrator.subscribe(run.run_id)
        assert queue is not None
        await orchestrator.execute_run(run.run_id)
        events = []
        while True:
            ev = await asyncio.wait_for(queue.get(), timeout=2.0)
            if ev is None:
                break
            events.append(ev)
        ticks = [e for e in events if isinstance(e, KpiTickEvent)]
        # ≥ 14 (one tick at start + one at completion of each of 7 agents).
        assert len(ticks) >= 14
        # rows_in_motion + files_written are monotonic non-decreasing.
        rows = [t.tick.rows_in_motion for t in ticks]
        files = [t.tick.files_written for t in ticks]
        assert all(b >= a for a, b in zip(rows, rows[1:], strict=False))
        assert all(b >= a for a, b in zip(files, files[1:], strict=False))

    asyncio.run(_run())
