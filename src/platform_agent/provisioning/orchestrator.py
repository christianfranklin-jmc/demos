"""Provisioning orchestrator (T077, US3 / R6).

Runs the 7-agent DAG with the dependency edges:

    schema → pipeline → model → quality → mapping → {semantic, delivery}

State is held in-memory keyed by `run_id`. The orchestrator emits v2
SSE events as it advances; consumers attach via
``GET /workflow/provision/{run_id}/events``. Failed agents flip to
RETRYING; only the failed agent + its downstream dependents re-run on
``POST /workflow/provision/{run_id}/retry`` (FR-029).
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import threading
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from platform_agent.provisioning.agents import (
    delivery_agent,
    mapping_agent,
    model_agent,
    pipeline_agent,
    quality_agent,
    schema_agent,
    semantic_agent,
)
from platform_agent.provisioning.agents._base import AgentContext, AgentRunner
from platform_agent.provisioning.events import (
    AgentCompletedEvent,
    AgentFailedEvent,
    AgentProgressEvent,
    AgentStartedEvent,
    ArtifactProducedEvent,
    KpiTickEvent,
    ProvisionEvent,
    RunCompletedEvent,
    RunNeedsReplanEvent,
)
from platform_agent.provisioning.models import (
    AgentExecution,
    AgentId,
    AgentState,
    Artifact,
    KpiTick,
    ProductState,
    ProvisioningRun,
    RunState,
)
from platform_agent.workflow.pill_models import PRDDraft
from platform_agent.workspace.activity_log import write as log_activity
from platform_agent.workspace.activity_models import ActivityKind

logger = logging.getLogger(__name__)


# DAG: agent → list of upstream dependencies.
DAG_DEPS: dict[AgentId, list[AgentId]] = {
    AgentId.SCHEMA: [],
    AgentId.PIPELINE: [AgentId.SCHEMA],
    AgentId.MODEL: [AgentId.PIPELINE],
    AgentId.QUALITY: [AgentId.MODEL],
    AgentId.MAPPING: [AgentId.QUALITY],
    AgentId.SEMANTIC: [AgentId.MAPPING],
    AgentId.DELIVERY: [AgentId.MAPPING, AgentId.SEMANTIC],
}

DAG_ORDER: list[AgentId] = [
    AgentId.SCHEMA,
    AgentId.PIPELINE,
    AgentId.MODEL,
    AgentId.QUALITY,
    AgentId.MAPPING,
    AgentId.SEMANTIC,
    AgentId.DELIVERY,
]

AGENT_RUNNERS: dict[AgentId, AgentRunner] = {
    AgentId.SCHEMA: schema_agent.run,
    AgentId.PIPELINE: pipeline_agent.run,
    AgentId.MODEL: model_agent.run,
    AgentId.QUALITY: quality_agent.run,
    AgentId.MAPPING: mapping_agent.run,
    AgentId.SEMANTIC: semantic_agent.run,
    AgentId.DELIVERY: delivery_agent.run,
}


# ───── In-memory run registry ─────


class _RunRecord:
    """Per-run state held in process memory."""

    __slots__ = ("run", "prd", "queue", "subscribers", "lock")

    def __init__(self, run: ProvisioningRun, prd: PRDDraft) -> None:
        self.run = run
        self.prd = prd
        # Each event stream gets its own bounded queue so slow consumers
        # don't block the orchestrator.
        self.subscribers: list[asyncio.Queue[ProvisionEvent | None]] = []
        self.lock = threading.RLock()
        self.queue: list[ProvisionEvent] = []  # backlog for late attachers


_runs: dict[str, _RunRecord] = {}
_runs_lock = threading.RLock()


def get_run(run_id: str) -> ProvisioningRun | None:
    with _runs_lock:
        record = _runs.get(run_id)
    return record.run if record else None


def get_run_record(run_id: str) -> _RunRecord | None:
    with _runs_lock:
        return _runs.get(run_id)


def subscribe(run_id: str) -> asyncio.Queue[ProvisionEvent | None] | None:
    """Attach an SSE consumer; returns a queue. Backlog events flush first."""
    record = get_run_record(run_id)
    if record is None:
        return None
    q: asyncio.Queue[ProvisionEvent | None] = asyncio.Queue(maxsize=1024)
    with record.lock:
        for ev in record.queue:
            q.put_nowait(ev)
        record.subscribers.append(q)
    return q


def unsubscribe(run_id: str, q: asyncio.Queue[ProvisionEvent | None]) -> None:
    record = get_run_record(run_id)
    if record is None:
        return
    with record.lock:
        if q in record.subscribers:
            record.subscribers.remove(q)


# ───── Public API ─────


def queue_run(*, workspace_id: str, prd: PRDDraft) -> ProvisioningRun:
    """Materialize a ProvisioningRun and register it. Caller starts execution."""
    run = ProvisioningRun(
        run_id=str(uuid.uuid4()),
        workspace_id=uuid.UUID(workspace_id),
        prd_id=prd.prd_id or "",
        target_connection_id=prd.target.connection_id,
        state=RunState.QUEUED,
        agents=[
            AgentExecution(agent_id=aid, state=AgentState.PENDING)
            for aid in DAG_ORDER
        ],
    )
    record = _RunRecord(run=run, prd=prd)
    with _runs_lock:
        _runs[run.run_id] = record
    return run


async def execute_run(run_id: str) -> None:
    """Drive the DAG to completion. Idempotent against double-execution."""
    record = get_run_record(run_id)
    if record is None:
        raise KeyError(run_id)
    run = record.run
    with record.lock:
        if run.state in (RunState.RUNNING, RunState.COMPLETED):
            return
        run.state = RunState.RUNNING
        run.started_at = datetime.now(tz=UTC)

    log_activity(
        connection_id=run.target_connection_id,
        workspace_id=run.workspace_id,
        kind=ActivityKind.PROVISIONING_STARTED,
        payload={"run_id": run.run_id, "prd_id": run.prd_id},
    )

    # Per-run sequence counter for v2 envelope ordering.
    seq_state: dict[str, int] = {"n": 0}

    def _next_seq() -> int:
        seq_state["n"] += 1
        return seq_state["n"]

    def _emit(event: ProvisionEvent) -> None:
        with record.lock:
            record.queue.append(event)
            for q in list(record.subscribers):
                try:
                    q.put_nowait(event)
                except asyncio.QueueFull:
                    logger.warning("dropping event for slow subscriber")

    # KPI ticker — fires on a schedule + whenever an artifact is produced.
    state = {
        "rows_in_motion": 0,
        "agents_active": 0,
        "files_written": 0,
    }

    def _kpi_tick() -> None:
        tick = KpiTick(
            ts=datetime.now(tz=UTC),
            rows_in_motion=state["rows_in_motion"],
            agents_active=state["agents_active"],
            files_written=state["files_written"],
        )
        run.kpi_series.append(tick)
        _emit(KpiTickEvent(run_id=run.run_id, seq=_next_seq(), tick=tick))

    upstream_artifacts: dict[AgentId, list[Artifact]] = {}

    for agent_id in DAG_ORDER:
        execution = next(a for a in run.agents if a.agent_id == agent_id)
        # Skip agents that already completed (rerun path); orchestrator's
        # caller is responsible for resetting failed agents to pending.
        if execution.state == AgentState.COMPLETED:
            upstream_artifacts[agent_id] = list(execution.artifacts)
            continue

        execution.state = AgentState.ACTIVE
        execution.started_at = datetime.now(tz=UTC)
        execution.attempt += 1 if execution.attempt > 1 else 0  # noqa: PLW0127 — keep attempt at 1 on first run
        if execution.attempt == 0:
            execution.attempt = 1
        state["agents_active"] += 1
        _emit(
            AgentStartedEvent(
                run_id=run.run_id,
                seq=_next_seq(),
                agent_id=agent_id,
                attempt=execution.attempt,
            )
        )
        _kpi_tick()

        # Bind aid into the closure so each agent's emit calls land on the
        # right agent_id; mypy needs explicit annotations on these closures.
        bound_agent: AgentId = agent_id

        def _progress(msg: str, aid: AgentId = bound_agent) -> None:
            _emit(
                AgentProgressEvent(
                    run_id=run.run_id,
                    seq=_next_seq(),
                    agent_id=aid,
                    message=msg,
                )
            )

        def _artifact(art: Artifact, aid: AgentId = bound_agent) -> None:
            _on_artifact(art, aid, state, _emit, _next_seq, run.run_id)

        ctx = AgentContext(
            run_id=run.run_id,
            workspace_id=str(run.workspace_id),
            target_connection_id=run.target_connection_id,
            prd=record.prd,
            upstream_artifacts={k: list(v) for k, v in upstream_artifacts.items()},
            emit_progress=_progress,
            emit_artifact=_artifact,
        )
        try:
            output = await asyncio.to_thread(AGENT_RUNNERS[agent_id], ctx)
        except Exception as exc:  # noqa: BLE001
            logger.exception("agent %s failed", agent_id)
            # Tiny stand-in so the failure path is uniform with AgentOutput.
            output = type(
                "Out",
                (),
                {
                    "artifacts": [],
                    "error": {
                        "code": "exception",
                        "message": str(exc),
                        "retryable": True,
                    },
                    "latency_ms_p95": None,
                },
            )()

        state["agents_active"] -= 1
        execution.completed_at = datetime.now(tz=UTC)
        execution.artifacts = list(output.artifacts)
        execution.latency_ms_p95 = output.latency_ms_p95

        if output.error:
            from platform_agent.provisioning.models import AgentError as AgentErrorModel

            execution.state = AgentState.FAILED
            execution.error = AgentErrorModel(**output.error)
            _emit(
                AgentFailedEvent(
                    run_id=run.run_id,
                    seq=_next_seq(),
                    agent_id=agent_id,
                    error_code=output.error["code"],
                    error_message=output.error["message"],
                    retryable=output.error.get("retryable", True),
                )
            )
            _kpi_tick()
            # Mapping is the gate that registers the product. A failure
            # before/at mapping means no product; everything after still
            # registers a (provisional) product per Q5.
            pre_mapping = (
                AgentId.SCHEMA,
                AgentId.PIPELINE,
                AgentId.MODEL,
                AgentId.QUALITY,
                AgentId.MAPPING,
            )
            if agent_id in pre_mapping:
                run.state = RunState.FAILED
            else:
                run.state = RunState.NEEDS_REPLAN
            run.completed_at = datetime.now(tz=UTC)
            _emit(
                RunNeedsReplanEvent(
                    run_id=run.run_id,
                    seq=_next_seq(),
                    reason=output.error["message"],
                    suggested_agent=agent_id,
                )
            )
            return

        execution.state = AgentState.COMPLETED
        upstream_artifacts[agent_id] = list(output.artifacts)
        _emit(
            AgentCompletedEvent(
                run_id=run.run_id,
                seq=_next_seq(),
                agent_id=agent_id,
                artifacts=[a.model_dump(mode="json") for a in output.artifacts],
                latency_ms_p95=execution.latency_ms_p95,
            )
        )
        _kpi_tick()

    # Run summary (delivery_agent set the product state).
    final_product = _final_product(run, upstream_artifacts)
    if final_product is not None:
        run.final_product_id = final_product.get("product_id")
        pass_rate = float(final_product.get("validation_pass_rate", 0.0))
        run.validation_pass_rate = pass_rate
        is_final = final_product.get("state") == ProductState.FINAL.value
        run.state = RunState.COMPLETED if is_final else RunState.NEEDS_REPLAN
        _emit(
            RunCompletedEvent(
                run_id=run.run_id,
                seq=_next_seq(),
                product_id=str(final_product["product_id"]),
                product_state=("final" if is_final else "provisional"),
                validation_pass_rate=pass_rate,
            )
        )
        if not is_final:
            _emit(
                RunNeedsReplanEvent(
                    run_id=run.run_id,
                    seq=_next_seq(),
                    reason=f"validation pass rate {pass_rate:.0%} below threshold",
                    suggested_agent=AgentId.DELIVERY,
                )
            )
    else:
        run.state = RunState.FAILED

    run.completed_at = datetime.now(tz=UTC)
    # Signal end-of-stream to subscribers.
    with record.lock:
        for q in list(record.subscribers):
            with contextlib.suppress(asyncio.QueueFull):
                q.put_nowait(None)


def _on_artifact(
    art: Artifact,
    agent_id: AgentId,
    state: dict[str, int],
    emit: Callable[[ProvisionEvent], None],
    next_seq: Callable[[], int],
    run_id: str,
) -> None:
    if art.kind in {"source_pull", "staging_parquet", "iceberg_table"}:
        rows = int(art.meta.get("rows", 0)) if art.meta else 0
        state["rows_in_motion"] += rows
    if art.kind in {"dbt_model", "iceberg_table", "staging_parquet"}:
        state["files_written"] += 1
    emit(
        ArtifactProducedEvent(
            run_id=run_id,
            seq=next_seq(),
            agent_id=agent_id,
            artifact=art.model_dump(mode="json"),
        )
    )


def _final_product(
    run: ProvisioningRun, upstream: dict[AgentId, list[Artifact]]
) -> dict[str, Any] | None:
    """Return the latest IcebergDataProduct dict from the delivery agent (or mapping fallback)."""
    for aid in (AgentId.DELIVERY, AgentId.MAPPING):
        for art in upstream.get(aid, []):
            if art.kind == "iceberg_data_product":
                return dict(art.meta)
    return None


def reset_for_retry(run_id: str, agent_id: AgentId) -> bool:
    """Reset the named agent + everything downstream to PENDING for rerun."""
    record = get_run_record(run_id)
    if record is None:
        return False
    run = record.run
    with record.lock:
        # Find the index of the agent in DAG_ORDER and reset from there.
        try:
            start = DAG_ORDER.index(agent_id)
        except ValueError:
            return False
        for execution in run.agents:
            if DAG_ORDER.index(execution.agent_id) >= start:
                execution.state = AgentState.PENDING
                execution.error = None
                execution.attempt += 1
                execution.started_at = None
                execution.completed_at = None
                execution.artifacts = []
        run.state = RunState.QUEUED
        run.completed_at = None
    return True


# Test/harness hook to clear runs between cases.
def _reset_runs() -> None:
    with _runs_lock:
        _runs.clear()


__all__ = [
    "DAG_DEPS",
    "DAG_ORDER",
    "queue_run",
    "execute_run",
    "get_run",
    "get_run_record",
    "subscribe",
    "unsubscribe",
    "reset_for_retry",
    "_reset_runs",
]
