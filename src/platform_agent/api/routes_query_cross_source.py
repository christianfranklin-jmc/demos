"""Cross-source TTYD route (T095, US4).

POST /workflow/query/cross-source — accepts a question + lens + a
caller-supplied per-source pull plan + join SQL, executes the pulls
against the right DatabaseDrivers, joins them in a DuckDB scratchpad,
and returns a structured response with `sources_used`, the join step,
KPI snapshot, and the natural-language answer.

V1 is **planner-light**: the caller provides the pulls and join SQL.
The Strands/Bedrock NL→SQL planner that turns a free-text question
into the full plan is reserved for ADR-018 D2 — same swap-pattern as
the pill_generator (ADR-021 D2).
"""

from __future__ import annotations

import logging
import time
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from platform_agent.api.deps import SessionContext, get_session_context
from platform_agent.api.routes_workspace import get_credentials
from platform_agent.drivers import DRIVER_REGISTRY
from platform_agent.tools.duckdb_scratchpad import (
    CrossSourceQueryRequest,
    CrossSourceQueryResult,
    SourcePullResult,
    cross_source_query,
)
from platform_agent.workspace.activity_log import write as log_activity
from platform_agent.workspace.activity_models import ActivityKind
from platform_agent.workspace.models import Connection, ConnectionStatus, DriverType
from platform_agent.workspace.read_only import ReadOnlyViolation, assert_read_only
from platform_agent.workspace.registry import get_registry

logger = logging.getLogger(__name__)
router = APIRouter(tags=["ttyd-cross-source"])


# ───── Request / response shapes ─────


class SourcePullSpec(BaseModel):
    connection_id: str
    sql: str
    view_name: str = Field(..., pattern=r"^[A-Za-z_][A-Za-z0-9_]*$")
    max_rows: int = Field(default=250, ge=1, le=250)


class CrossSourceTtydRequest(BaseModel):
    question: str = Field(..., min_length=1)
    lens: str = Field(default="all", pattern=r"^(all|connection)$")
    pulls: list[SourcePullSpec]
    join_sql: str
    join_cap: int = Field(default=5000, ge=1, le=5000)


class SourceChip(BaseModel):
    connection_id: str
    driver_type: str
    scope: str
    rows: int
    truncated_at_cap: bool
    view_name: str
    chip_label: str


class TtydKPISnapshot(BaseModel):
    queries_answered_today: int
    avg_latency_ms: int
    sources_used_today: int
    semantic_hit_rate: float


class CrossSourceTtydResponse(BaseModel):
    answer: str
    join_result: CrossSourceQueryResult
    sources_used: list[SourceChip]
    kpi_snapshot: TtydKPISnapshot
    latency_ms: int


# ───── Module-local KPI accumulator (in-memory) ─────

_kpi: dict[str, dict[str, Any]] = {}


def _record_kpi(workspace_id: UUID, latency_ms: int, sources: int) -> TtydKPISnapshot:
    key = str(workspace_id)
    bucket = _kpi.setdefault(
        key, {"queries": 0, "latency_sum_ms": 0, "sources_seen": set()}
    )
    bucket["queries"] = int(bucket["queries"]) + 1
    bucket["latency_sum_ms"] = int(bucket["latency_sum_ms"]) + latency_ms
    bucket["sources_seen"].update([f"src{i}" for i in range(sources)])
    avg = (
        int(bucket["latency_sum_ms"]) // int(bucket["queries"])
        if bucket["queries"]
        else 0
    )
    return TtydKPISnapshot(
        queries_answered_today=int(bucket["queries"]),
        avg_latency_ms=avg,
        sources_used_today=len(bucket["sources_seen"]),
        # Semantic-hit tracking lands with US5; v1 keeps it 0 so the chip
        # appears with a deterministic value rather than an unbound float.
        semantic_hit_rate=0.0,
    )


# ───── Endpoint ─────


@router.post(
    "/workflow/query/cross-source",
    response_model=CrossSourceTtydResponse,
)
async def post_cross_source(
    payload: CrossSourceTtydRequest,
    ctx: Annotated[SessionContext, Depends(get_session_context)],
) -> CrossSourceTtydResponse:
    started = time.perf_counter()

    # FR-015: lens=all + ≥2 live connections required.
    ws = get_registry().get_or_create(ctx.session_id)
    live = ws.live_connections()
    if payload.lens == "all" and len(live) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "cross_source_unavailable",
                "message": "Cross-source TTYD requires ≥2 live connections.",
            },
        )

    # SC-006: read-only on every SQL we touch.
    for pull in payload.pulls:
        try:
            assert_read_only(pull.sql)
        except ReadOnlyViolation as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "read_only_violation", "message": str(exc)},
            ) from exc
    try:
        assert_read_only(payload.join_sql)
    except ReadOnlyViolation as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "read_only_violation", "message": str(exc)},
        ) from exc

    # Execute each pull through the connection's driver (max 250 rows).
    pull_results: list[SourcePullResult] = []
    chips: list[SourceChip] = []
    by_id: dict[str, Connection] = {c.connection_id: c for c in live}
    for spec in payload.pulls:
        conn = by_id.get(spec.connection_id)
        if conn is None or conn.status != ConnectionStatus.LIVE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "connection_unavailable",
                    "message": f"connection {spec.connection_id} is not live",
                },
            )
        result = _run_pull(conn, spec, ctx.session_id)
        pull_results.append(result)
        chips.append(_chip_for(conn, result))

    # Join in DuckDB.
    join = cross_source_query(
        CrossSourceQueryRequest(
            pulls=pull_results,
            join_sql=payload.join_sql,
            join_cap=payload.join_cap,
        )
    )

    latency_ms = int((time.perf_counter() - started) * 1000)
    answer = _summarize_answer(payload.question, join, chips)

    log_activity(
        connection_id=pull_results[0].connection_id if pull_results else "—",
        workspace_id=ctx.session_id,
        kind=ActivityKind.TTYD_QUERY,
        payload={
            "question": payload.question,
            "lens": payload.lens,
            "sources_used": [c.connection_id for c in chips],
            "rows_returned": join.rows_returned,
            "latency_ms": latency_ms,
        },
    )

    kpi = _record_kpi(ctx.session_id, latency_ms, len(chips))
    return CrossSourceTtydResponse(
        answer=answer,
        join_result=join,
        sources_used=chips,
        kpi_snapshot=kpi,
        latency_ms=latency_ms,
    )


# ───── Helpers ─────


def _run_pull(
    conn: Connection, spec: SourcePullSpec, workspace_id: UUID
) -> SourcePullResult:
    """Execute a single per-source pull through the right DatabaseDriver."""
    creds = get_credentials(workspace_id, conn.connection_id) or {}
    cls = DRIVER_REGISTRY.get(conn.driver_type.value)
    if cls is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "driver_missing",
                "message": f"no driver for {conn.driver_type.value}",
            },
        )
    kwargs: dict[str, Any] = {**creds}
    if conn.driver_type == DriverType.POSTGRESQL:
        host, _, port = conn.endpoint.partition(":")
        kwargs.setdefault("host", host)
        kwargs.setdefault("port", int(port) if port else 5432)
        kwargs.setdefault("database", conn.scope.split(".")[0])
    elif conn.driver_type == DriverType.ICEBERG:
        kwargs.setdefault("glue_database", conn.scope)
        kwargs.setdefault(
            "warehouse_s3_uri", creds.get("warehouse_s3_uri", "s3://placeholder/warehouse")
        )
        kwargs.setdefault("region", creds.get("region", "us-east-1"))

    import contextlib

    driver = cls(**kwargs)
    driver.connect()
    try:
        result = driver.execute_query(spec.sql, max_rows=spec.max_rows)
    finally:
        with contextlib.suppress(Exception):
            driver.close()

    columns: list[str] = list(result.get("columns", []))
    rows: list[dict[str, Any]] = list(result.get("rows", []))
    if not columns and rows:
        columns = list(rows[0].keys())
    return SourcePullResult(
        connection_id=conn.connection_id,
        view_name=spec.view_name,
        columns=columns,
        rows=rows[: spec.max_rows],
        truncated_at_cap=bool(result.get("truncated", len(rows) >= spec.max_rows)),
    )


def _chip_for(conn: Connection, result: SourcePullResult) -> SourceChip:
    icon = {
        "postgresql": "🐘",
        "redshift": "🔴",
        "snowflake": "❄",
        "databricks": "🧱",
        "iceberg": "🧊",
    }.get(conn.driver_type.value, "•")
    return SourceChip(
        connection_id=conn.connection_id,
        driver_type=conn.driver_type.value,
        scope=conn.scope,
        rows=len(result.rows),
        truncated_at_cap=result.truncated_at_cap,
        view_name=result.view_name,
        chip_label=(
            f"{icon} {conn.display_name} · {conn.scope} · {len(result.rows)} rows"
            + (" (capped)" if result.truncated_at_cap else "")
        ),
    )


def _summarize_answer(
    question: str,
    join: CrossSourceQueryResult,
    chips: list[SourceChip],
) -> str:
    """Compose a natural-language answer from the join result.

    v1 is deterministic — it summarizes row counts and source contributions.
    The LLM-driven NL response (R4 D2) is a single-function replacement.
    """
    src_summary = ", ".join(
        f"{c.connection_id[:8]}({c.rows} rows)" for c in chips
    )
    cap = " (capped)" if join.truncated_at_cap else ""
    return (
        f'Answered "{question}" by joining {len(chips)} sources [{src_summary}] '
        f"into {join.rows_returned} rows{cap}. Top columns: "
        + ", ".join(join.columns[:6])
    )


def _reset_kpi() -> None:
    _kpi.clear()


__all__ = ["router", "_reset_kpi"]
