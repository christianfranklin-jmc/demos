"""Redundancy gate routes (T117, US6 / FR-026, R7).

POST /workflow/redundancy-check                      — score PRD against
                                                       target connection
POST /workflow/redundancy-check/{report_id}/decide   — record reuse-or-
                                                       override decisions

The gate compares a PRDDraft's `entities_proposed` and `metrics_proposed`
against the target Iceberg connection's existing semantic graph
(per Q2: ONLY the target connection — never source connections).

v1 implementation is deterministic (name + attribute overlap). The
LLM-driven `redundancy-agent` (R7 D2) plugs in here later — same swap
pattern as ADR-018 and ADR-021.
"""

from __future__ import annotations

import logging
import threading
from datetime import UTC, datetime
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from platform_agent.api.deps import SessionContext, get_session_context
from platform_agent.provisioning.models import (
    Decision,
    DecisionKind,
    OverlapItem,
    OverlapKind,
    RedundancyReport,
    RedundancyState,
)
from platform_agent.semantic.store import make_store
from platform_agent.workflow.pill_models import PRDDraft
from platform_agent.workspace.activity_log import write as log_activity
from platform_agent.workspace.activity_models import ActivityKind
from platform_agent.workspace.models import ConnectionStatus, DriverType
from platform_agent.workspace.registry import get_registry

logger = logging.getLogger(__name__)
router = APIRouter(tags=["redundancy"])

# ───── In-memory report registry (per process) ─────

_reports: dict[str, RedundancyReport] = {}
_reports_lock = threading.RLock()


def get_report(report_id: str) -> RedundancyReport | None:
    with _reports_lock:
        return _reports.get(report_id)


def _put_report(report: RedundancyReport) -> None:
    with _reports_lock:
        _reports[report.report_id] = report


def _reset_reports() -> None:
    with _reports_lock:
        _reports.clear()


# ───── Request / response shapes ─────


class RedundancyCheckRequest(BaseModel):
    prd: PRDDraft


class DecideRequest(BaseModel):
    decisions: list[Decision] = Field(default_factory=list)
    override_rationale: str | None = None


class DecideResponse(BaseModel):
    cleared_to_provision: bool
    state: RedundancyState
    pending_overlaps: int


# ───── Endpoints ─────


@router.post("/workflow/redundancy-check", response_model=RedundancyReport)
async def post_check(
    payload: RedundancyCheckRequest,
    ctx: Annotated[SessionContext, Depends(get_session_context)],
) -> RedundancyReport:
    target_cid = payload.prd.target.connection_id

    # FR-026 + Q3: target must be a live iceberg connection in this workspace.
    ws = get_registry().get_or_create(ctx.session_id)
    target_conn = next(
        (
            c
            for c in ws.connections
            if c.connection_id == target_cid
            and c.driver_type == DriverType.ICEBERG
            and c.status == ConnectionStatus.LIVE
        ),
        None,
    )
    if target_conn is None:
        # The pill generator emits ICEBERG_TARGET_REQUIRED when no Iceberg
        # connection was live at pill-generation time. Surface the same code
        # the provision route uses so the frontend can prompt the user.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "no_iceberg_target",
                "message": (
                    "Redundancy check requires the PRD target to be a live "
                    "Iceberg/Glue connection in this workspace."
                ),
            },
        )

    # Read the target connection's existing graph.
    store = make_store(target_cid)
    try:
        existing_entities = store.list_entities()
        existing_metrics = store.list_metrics()
    finally:
        store.close()

    overlaps: list[OverlapItem] = []
    for proposed in payload.prd.entities_proposed:
        match = next(
            (e for e in existing_entities if e.name.lower() == proposed.name.lower()),
            None,
        )
        if match is None:
            continue
        # Attribute-name overlap percentage.
        proposed_attrs = {a.name.lower() for a in proposed.attributes}
        existing_attrs = {a.name.lower() for a in match.attributes}
        if proposed_attrs:
            common = proposed_attrs & existing_attrs
            overlap_pct = (len(common) / len(proposed_attrs)) * 100.0
        else:
            overlap_pct = 100.0  # no attributes to compare → name-match only
        diff = _build_diff(proposed.name, list(proposed_attrs), list(existing_attrs))
        overlaps.append(
            OverlapItem(
                proposed_name=proposed.name,
                existing_id=match.entity_id,
                kind=OverlapKind.ENTITY,
                overlap_pct=round(overlap_pct, 2),
                side_by_side_diff=diff,
            )
        )

    for proposed_metric in payload.prd.metrics_proposed:
        match_metric = next(
            (
                m
                for m in existing_metrics
                if m.name.lower() == proposed_metric.name.lower()
            ),
            None,
        )
        if match_metric is None:
            continue
        # Metric overlap percentage = 100 if SQL identical; 50 if only the
        # name matched. v1 keeps the heuristic simple.
        same_sql = (
            proposed_metric.definition_sql.strip().lower()
            == match_metric.definition_sql.strip().lower()
        )
        overlaps.append(
            OverlapItem(
                proposed_name=proposed_metric.name,
                existing_id=match_metric.metric_id,
                kind=OverlapKind.METRIC,
                overlap_pct=100.0 if same_sql else 50.0,
                side_by_side_diff=(
                    f"existing: `{match_metric.definition_sql[:80]}`\n"
                    f"proposed: `{proposed_metric.definition_sql[:80]}`"
                ),
            )
        )

    proposed_count = len(payload.prd.entities_proposed) + len(payload.prd.metrics_proposed)
    state = _state_from_overlaps(overlaps, proposed_count)
    report = RedundancyReport(
        report_id=str(uuid4()),
        prd_id=payload.prd.prd_id or "",
        target_connection_id=target_cid,
        state=state,
        overlaps=overlaps,
        decisions=[],
        override_rationale=None,
        generated_at=datetime.now(tz=UTC),
        cleared_to_provision=(state == RedundancyState.NET_NEW),
    )
    _put_report(report)

    log_activity(
        connection_id=target_cid,
        workspace_id=ctx.session_id,
        kind=ActivityKind.REDUNDANCY_DECISION,
        payload={
            "report_id": report.report_id,
            "state": state.value,
            "overlaps": len(overlaps),
            "auto_cleared": report.cleared_to_provision,
        },
    )
    return report


@router.post(
    "/workflow/redundancy-check/{report_id}/decide",
    response_model=DecideResponse,
)
async def post_decide(
    report_id: str,
    payload: DecideRequest,
    ctx: Annotated[SessionContext, Depends(get_session_context)],  # noqa: ARG001
) -> DecideResponse:
    report = get_report(report_id)
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    # Build a per-overlap decision lookup. Decisions reference
    # `overlap.existing_id`.
    by_existing: dict[str, Decision] = {d.overlap_existing_id: d for d in payload.decisions}
    pending = 0
    has_override = False
    for overlap in report.overlaps:
        decision = by_existing.get(overlap.existing_id)
        if decision is None:
            pending += 1
            continue
        no_rationale = not (decision.rationale or payload.override_rationale)
        if decision.kind == DecisionKind.OVERRIDE and no_rationale:
            # An override without a rationale isn't acceptable.
            pending += 1
            continue
        if decision.kind == DecisionKind.OVERRIDE:
            has_override = True

    cleared = False
    if report.state == RedundancyState.NET_NEW:
        cleared = True
    elif report.state == RedundancyState.PARTIAL_OVERLAP:
        cleared = pending == 0
    elif report.state == RedundancyState.DUPLICATE:
        cleared = bool(payload.override_rationale and pending == 0 and has_override)

    if cleared:
        # Persist the decisions on the report so the provision route can
        # consult cleared_to_provision later.
        updated = report.model_copy(
            update={
                "decisions": list(payload.decisions),
                "override_rationale": payload.override_rationale,
                "cleared_to_provision": True,
            }
        )
        _put_report(updated)

    return DecideResponse(
        cleared_to_provision=cleared,
        state=report.state,
        pending_overlaps=pending,
    )


# ───── Helpers ─────


def _state_from_overlaps(
    overlaps: list[OverlapItem], proposed_count: int
) -> RedundancyState:
    if not overlaps:
        return RedundancyState.NET_NEW
    if proposed_count > 0 and len(overlaps) == proposed_count and all(
        o.overlap_pct >= 80.0 for o in overlaps
    ):
        return RedundancyState.DUPLICATE
    return RedundancyState.PARTIAL_OVERLAP


def _build_diff(
    name: str, proposed_attrs: list[str], existing_attrs: list[str]
) -> str:
    only_existing = sorted(set(existing_attrs) - set(proposed_attrs))
    only_proposed = sorted(set(proposed_attrs) - set(existing_attrs))
    common = sorted(set(proposed_attrs) & set(existing_attrs))
    return (
        f"`{name}` exists in target connection's graph.\n"
        f"common attributes: {', '.join(common) or '—'}\n"
        f"only existing: {', '.join(only_existing) or '—'}\n"
        f"only proposed: {', '.join(only_proposed) or '—'}"
    )


__all__ = ["router", "get_report", "_reset_reports"]
