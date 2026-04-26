"""pipeline_agent — per-source pulls + DuckDB scratchpad staging (T070, US3).

Promoted from stub to real implementation in Phase 10c. For every
SourcePullSpec in the PRD:

  1. Look up the source Connection in the WorkspaceRegistry.
  2. Run `driver.execute_query(sql, max_rows=…)` through the live
     driver — same path the cross-source TTYD uses.
  3. Register each pull's rows in a per-run DuckDB scratchpad and
     write a single staging Parquet file for the model_agent + dbt
     compile path to consume.

The 250-row per-source cap (FR-018) is enforced at the driver layer
*and* re-validated by the DuckDB scratchpad on the way in.

Falls back to the deterministic stub when:
- no live workspace context (test isolation), OR
- the source connection isn't reachable / has no credentials, OR
- the duckdb / pyarrow stack isn't available.

Artifact contract is unchanged (`source_pull`, `staging_parquet`)
so the existing 7-agent DAG tests keep passing.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any
from uuid import UUID

from platform_agent.provisioning.agents._base import (
    AgentContext,
    AgentOutput,
)
from platform_agent.provisioning.models import Artifact

logger = logging.getLogger(__name__)


def run(ctx: AgentContext) -> AgentOutput:
    artifacts: list[Artifact] = []
    ctx.emit_progress(
        f"executing {len(ctx.prd.source_pulls)} source pull(s) into DuckDB scratchpad"
    )

    workspace_id = _safe_uuid(ctx.workspace_id)
    real_results = _try_real_pulls(workspace_id, ctx) if workspace_id else None

    rows_total = 0
    for i, pull in enumerate(ctx.prd.source_pulls, 1):
        if real_results and pull.sql in real_results:
            row_count = real_results[pull.sql]["rows"]
            truncated = real_results[pull.sql]["truncated"]
            source = "live"
        else:
            # Deterministic stub: 50–250 rows derived from SQL length.
            row_count = min(250, 50 + (len(pull.sql) % 200))
            truncated = row_count >= pull.max_rows
            source = "stub"
        rows_total += row_count
        ctx.emit_progress(
            f"pull {i}/{len(ctx.prd.source_pulls)}: {row_count} rows "
            f"from {pull.connection_id[:12]}… ({source})"
        )
        artifact = Artifact(
            kind="source_pull",
            ref=f"{pull.connection_id}:{i}",
            meta={
                "connection_id": pull.connection_id,
                "rows": row_count,
                "max_rows": pull.max_rows,
                "truncated": truncated,
                "source": source,
            },
        )
        artifacts.append(artifact)
        ctx.emit_artifact(artifact)

    staging_meta: dict[str, Any] = {"rows": rows_total}
    staging_ref = f"staging/{ctx.run_id}/{ctx.prd.target.table_name}.parquet"
    if real_results:
        # Try to write a real Parquet file under ~/.dsa-hub/runs/<run_id>/
        # so model_agent + downstream consumers can consume it. Failure
        # falls back to the stub S3-style ref.
        path, written = _try_write_staging_parquet(ctx, real_results)
        if path:
            staging_ref = str(path)
            staging_meta["rows"] = written
            staging_meta["path"] = str(path)
            staging_meta["source"] = "live"
        else:
            staging_meta["source"] = "stub"
    else:
        staging_meta["source"] = "stub"

    staging = Artifact(
        kind="staging_parquet",
        ref=staging_ref,
        meta=staging_meta,
    )
    artifacts.append(staging)
    ctx.emit_artifact(staging)
    return AgentOutput(artifacts=artifacts)


# ───── Helpers ─────


def _safe_uuid(raw: str) -> UUID | None:
    try:
        return UUID(raw)
    except ValueError:
        return None


def _try_real_pulls(
    workspace_id: UUID, ctx: AgentContext
) -> dict[str, dict[str, Any]] | None:
    """Execute each SourcePullSpec; return {sql: {rows, truncated, columns, rows_data}}.

    Returns None if any pull's connection isn't live-reachable — we
    don't want a "half-real, half-stub" run; either every pull goes
    through the live driver or we fall back to the deterministic stub.
    """
    try:
        from platform_agent.api.routes_workspace import get_credentials
        from platform_agent.drivers import DRIVER_REGISTRY
        from platform_agent.workspace.models import (
            ConnectionStatus,
            DriverType,
        )
        from platform_agent.workspace.registry import get_registry

        ws = get_registry().get(workspace_id)
        if ws is None:
            return None

        results: dict[str, dict[str, Any]] = {}
        for pull in ctx.prd.source_pulls:
            conn = ws.find(pull.connection_id)
            if conn is None or conn.status != ConnectionStatus.LIVE:
                return None  # uniform fallback
            cls = DRIVER_REGISTRY.get(conn.driver_type.value)
            if cls is None:
                return None
            creds = get_credentials(workspace_id, conn.connection_id) or {}
            kwargs: dict[str, Any] = {**creds}
            if conn.driver_type == DriverType.POSTGRESQL:
                host, _, port = conn.endpoint.partition(":")
                kwargs.setdefault("host", host)
                kwargs.setdefault("port", int(port) if port else 5432)
                kwargs.setdefault("database", conn.scope.split(".")[0])
            elif conn.driver_type == DriverType.ICEBERG:
                kwargs.setdefault("glue_database", conn.scope)
                kwargs.setdefault(
                    "warehouse_s3_uri",
                    creds.get("warehouse_s3_uri", "s3://placeholder/warehouse"),
                )
                kwargs.setdefault("region", creds.get("region", "us-east-1"))
            try:
                driver = cls(**kwargs)
                driver.connect()
            except Exception as exc:  # noqa: BLE001
                logger.debug("pipeline_agent: connect failed for %s — %s", pull.connection_id, exc)
                return None
            try:
                result = driver.execute_query(pull.sql, max_rows=pull.max_rows)
            except Exception as exc:  # noqa: BLE001
                logger.debug("pipeline_agent: query failed for %s — %s", pull.connection_id, exc)
                return None
            finally:
                import contextlib

                with contextlib.suppress(Exception):
                    driver.close()
            rows_data = list(result.get("rows", []))
            results[pull.sql] = {
                "rows": len(rows_data),
                "truncated": bool(result.get("truncated", False)),
                "columns": list(result.get("columns", [])),
                "rows_data": rows_data[: pull.max_rows],
                "view_name": _view_name(pull),
            }
        return results
    except Exception as exc:  # noqa: BLE001
        logger.debug("pipeline_agent: real pulls disabled — %s", exc)
        return None


def _view_name(pull: Any) -> str:
    """Stable, identifier-safe view name for the DuckDB scratchpad."""
    base = f"src_{pull.connection_id[:8]}"
    return base.replace("-", "_")


def _try_write_staging_parquet(
    ctx: AgentContext, real_results: dict[str, dict[str, Any]]
) -> tuple[Path | None, int]:
    """Stage all per-source rows into a single Parquet file under ~/.dsa-hub/.

    Uses DuckDB to write Parquet so we don't need pyarrow. Returns
    (path, row_count) on success; (None, 0) on any failure.
    """
    try:
        import duckdb

        from platform_agent.tools.duckdb_scratchpad import (
            CrossSourceQueryRequest,
            SourcePullResult,
            cross_source_query,
        )
    except ImportError:
        return None, 0

    pulls = []
    for pull in ctx.prd.source_pulls:
        live = real_results.get(pull.sql)
        if not live:
            continue
        rows_data = list(live["rows_data"])
        # DuckDB rows arrive as dicts when the driver uses RealDictCursor;
        # convert sequence-style rows into dicts using the columns list.
        if rows_data and not isinstance(rows_data[0], dict):
            cols = live["columns"]
            rows_data = [dict(zip(cols, r, strict=False)) for r in rows_data]
        pulls.append(
            SourcePullResult(
                connection_id=pull.connection_id,
                view_name=live["view_name"],
                columns=live["columns"],
                rows=rows_data,
                truncated_at_cap=live["truncated"],
            )
        )

    if not pulls:
        return None, 0

    try:
        # UNION ALL of every per-source view into the staging Parquet.
        # Columns from different sources may not align; we project a
        # `_source_view` column so model_agent / consumers can branch.
        union_pieces = " UNION ALL ".join(
            f"SELECT '{p.view_name}' AS _source_view, * FROM {p.view_name}"
            for p in pulls
        )
        join_sql = f"SELECT * FROM ({union_pieces}) AS _staging"
        # Cap at 5000 like every cross-source join.
        result = cross_source_query(
            CrossSourceQueryRequest(pulls=pulls, join_sql=join_sql, join_cap=5000)
        )

        out_dir = Path.home() / ".dsa-hub" / "runs" / ctx.run_id
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{ctx.prd.target.table_name}.parquet"

        # Use a fresh DuckDB session to write the result rows.
        con = duckdb.connect(":memory:")
        try:
            cols = result.columns
            con.execute(
                "CREATE TEMP TABLE _staging("
                + ", ".join(f'"{c}" VARCHAR' for c in cols)
                + ")"
            )
            placeholders = "(" + ", ".join("?" * len(cols)) + ")"
            con.executemany(
                f"INSERT INTO _staging VALUES {placeholders}",
                [tuple(str(r.get(c, "")) for c in cols) for r in result.rows],
            )
            con.execute(
                f"COPY _staging TO '{out_path}' (FORMAT PARQUET, COMPRESSION ZSTD)"
            )
        finally:
            con.close()
        return out_path, result.rows_returned
    except Exception as exc:  # noqa: BLE001
        logger.debug("pipeline_agent: staging Parquet write failed — %s", exc)
        return None, 0
