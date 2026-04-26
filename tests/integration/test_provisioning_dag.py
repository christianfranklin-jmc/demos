"""Integration test — full 7-agent DAG run (T068, US3).

Drives a real PRDDraft through the orchestrator (not via FastAPI),
asserts every agent reaches a terminal state, validates the v2
event-stream ordering, and exercises both the success-promotion
(state=final) and threshold-fail (state=provisional → needs_replan)
paths via threshold env tuning.
"""

from __future__ import annotations

import asyncio
import tempfile
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from platform_agent.provisioning import orchestrator
from platform_agent.provisioning.events import (
    AgentCompletedEvent,
    AgentStartedEvent,
    KpiTickEvent,
    RunCompletedEvent,
)
from platform_agent.provisioning.models import AgentId, AgentState, RunState
from platform_agent.workflow.pill_models import IcebergTarget, PRDDraft, SourcePullSpec


@pytest.fixture(autouse=True)
def _isolate(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "DSA_HUB_CONNECTIONS_DIR", tempfile.mkdtemp(prefix="dsa-hub-test-")
    )
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    orchestrator._reset_runs()


def _prd(business_questions: list[str] | None = None) -> PRDDraft:
    return PRDDraft(
        prd_id=str(uuid4()),
        title="Client 360",
        target=IcebergTarget(
            connection_id="iceberg-conn-1",
            glue_db="pinnacle_360",
            table_name="fct_client_360",
        ),
        business_questions=business_questions or [
            "Q1: AUM-weighted advisor performance",
            "Q2: clients with >2 strategy meetings",
            "Q3: top-decile engagement scores",
            "Q4: meetings-per-AUM ratio",
        ],
        source_pulls=[
            SourcePullSpec(
                connection_id="pg-1",
                sql="SELECT * FROM crm.client LIMIT 250",
                max_rows=250,
            ),
            SourcePullSpec(
                connection_id="sf-1",
                sql=(
                    "SELECT * FROM ANALYTICS.FCT_AUM_HISTORY "
                    "WHERE snapshot_date >= CURRENT_DATE - 90 LIMIT 250"
                ),
                max_rows=250,
            ),
        ],
        standards_applied=["naming.kimball.fct_dim_prefixes"],
    )


def test_full_dag_runs_all_seven_agents() -> None:
    async def _run() -> None:
        run = orchestrator.queue_run(workspace_id=str(uuid4()), prd=_prd())
        # Subscribe BEFORE execute so we capture every event.
        queue = orchestrator.subscribe(run.run_id)
        assert queue is not None
        await orchestrator.execute_run(run.run_id)
        # Drain events until end-of-stream sentinel (None).
        events = []
        while True:
            ev = await asyncio.wait_for(queue.get(), timeout=2.0)
            if ev is None:
                break
            events.append(ev)
        # Every agent fired exactly one started + one completed event.
        started_ids = [
            e.agent_id for e in events if isinstance(e, AgentStartedEvent)
        ]
        completed_ids = [
            e.agent_id for e in events if isinstance(e, AgentCompletedEvent)
        ]
        assert started_ids == [
            AgentId.SCHEMA, AgentId.PIPELINE, AgentId.MODEL, AgentId.QUALITY,
            AgentId.MAPPING, AgentId.SEMANTIC, AgentId.DELIVERY,
        ]
        assert completed_ids == started_ids
        # KPI ticks emitted at every state transition (≥14 — 2 per agent).
        kpi_ticks = [e for e in events if isinstance(e, KpiTickEvent)]
        assert len(kpi_ticks) >= 14

    asyncio.run(_run())


def test_v2_envelope_on_every_event() -> None:
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
        for ev in events:
            assert ev.v == 2
            assert ev.run_id == run.run_id
            assert ev.seq >= 1
            assert ev.ts is not None
        # Sequence numbers strictly increase.
        seqs = [e.seq for e in events]
        assert seqs == sorted(seqs)
        assert len(set(seqs)) == len(seqs)

    asyncio.run(_run())


def test_run_completed_state_final_when_threshold_met(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """All-pass → product=final, run state=COMPLETED."""

    # Force every validation to pass (override the stub).
    def all_pass(ctx, question, index):
        from platform_agent.provisioning.models import (
            ValidationResult,
            ValidationState,
        )
        return ValidationResult(
            result_id=str(uuid4()),
            run_id=ctx.run_id,
            question=question,
            state=ValidationState.PASSED,
            sql_executed="SELECT 1",
            latency_ms=10,
            judge_reasoning="forced pass",
            evaluated_at=datetime.now(tz=UTC),
        )

    monkeypatch.setattr(
        "platform_agent.provisioning.agents.delivery_agent._simulate_validation",
        all_pass,
    )

    async def _run() -> None:
        run = orchestrator.queue_run(workspace_id=str(uuid4()), prd=_prd())
        queue = orchestrator.subscribe(run.run_id)
        assert queue is not None
        await orchestrator.execute_run(run.run_id)
        # Drain
        completed: RunCompletedEvent | None = None
        while True:
            ev = await asyncio.wait_for(queue.get(), timeout=2.0)
            if ev is None:
                break
            if isinstance(ev, RunCompletedEvent):
                completed = ev
        assert completed is not None
        assert completed.product_state == "final"
        assert completed.validation_pass_rate == 1.0

        snap = orchestrator.get_run(run.run_id)
        assert snap is not None
        assert snap.state == RunState.COMPLETED
        # Every agent recorded COMPLETED.
        states = [a.state for a in snap.agents]
        assert all(s == AgentState.COMPLETED for s in states)

    asyncio.run(_run())


def test_run_needs_replan_when_threshold_missed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """All-fail → product=provisional, run state=NEEDS_REPLAN."""

    def all_fail(ctx, question, index):
        from platform_agent.provisioning.models import (
            ValidationResult,
            ValidationState,
        )
        return ValidationResult(
            result_id=str(uuid4()),
            run_id=ctx.run_id,
            question=question,
            state=ValidationState.FAILED,
            sql_executed="SELECT 1",
            latency_ms=10,
            judge_reasoning="forced fail",
            evaluated_at=datetime.now(tz=UTC),
        )

    monkeypatch.setattr(
        "platform_agent.provisioning.agents.delivery_agent._simulate_validation",
        all_fail,
    )

    async def _run() -> None:
        run = orchestrator.queue_run(workspace_id=str(uuid4()), prd=_prd())
        queue = orchestrator.subscribe(run.run_id)
        assert queue is not None
        await orchestrator.execute_run(run.run_id)
        completed: RunCompletedEvent | None = None
        while True:
            ev = await asyncio.wait_for(queue.get(), timeout=2.0)
            if ev is None:
                break
            if isinstance(ev, RunCompletedEvent):
                completed = ev
        assert completed is not None
        assert completed.product_state == "provisional"
        assert completed.validation_pass_rate == 0.0

        snap = orchestrator.get_run(run.run_id)
        assert snap is not None
        assert snap.state == RunState.NEEDS_REPLAN

    asyncio.run(_run())


def test_retry_resets_only_target_and_downstream() -> None:
    async def _run() -> None:
        run = orchestrator.queue_run(workspace_id=str(uuid4()), prd=_prd())
        queue = orchestrator.subscribe(run.run_id)
        assert queue is not None
        await orchestrator.execute_run(run.run_id)
        # drain
        while True:
            ev = await asyncio.wait_for(queue.get(), timeout=2.0)
            if ev is None:
                break

        # Reset from MAPPING down. SCHEMA / PIPELINE / MODEL / QUALITY remain
        # COMPLETED; MAPPING + SEMANTIC + DELIVERY revert to PENDING.
        ok = orchestrator.reset_for_retry(run.run_id, AgentId.MAPPING)
        assert ok
        snap = orchestrator.get_run(run.run_id)
        assert snap is not None
        states = {a.agent_id: a.state for a in snap.agents}
        assert states[AgentId.SCHEMA] == AgentState.COMPLETED
        assert states[AgentId.QUALITY] == AgentState.COMPLETED
        assert states[AgentId.MAPPING] == AgentState.PENDING
        assert states[AgentId.SEMANTIC] == AgentState.PENDING
        assert states[AgentId.DELIVERY] == AgentState.PENDING
        assert snap.state == RunState.QUEUED

    asyncio.run(_run())


def test_subscribe_returns_none_for_unknown_run() -> None:
    assert orchestrator.subscribe("not-a-run") is None


def test_artifact_kinds_cover_the_dag() -> None:
    """Every expected artifact kind appears at least once in a successful run."""

    async def _run() -> None:
        run = orchestrator.queue_run(workspace_id=str(uuid4()), prd=_prd())
        await orchestrator.execute_run(run.run_id)
        snap = orchestrator.get_run(run.run_id)
        assert snap is not None
        kinds: set[str] = set()
        for execution in snap.agents:
            for art in execution.artifacts:
                kinds.add(art.kind)
        # Spot-check the load-bearing ones.
        for expected in (
            "source_schema",
            "iceberg_ddl_plan",
            "source_pull",
            "staging_parquet",
            "dbt_model",
            "dbt_test_run",
            "iceberg_table",
            "iceberg_data_product",
            "validation_result",
            "semantic_entity",
        ):
            # semantic_entity only appears when entities_proposed is non-empty.
            if expected == "semantic_entity":
                continue
            assert expected in kinds, f"missing artifact kind: {expected}"

    asyncio.run(_run())
