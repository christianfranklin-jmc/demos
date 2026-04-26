"""pipeline_agent — per-source pulls + DuckDB scratchpad staging (T070, US3).

v1 stub: simulates the bounded source pulls (250-row caps from FR-018)
and reports row counts per source. Real path (deferred): execute each
SourcePullSpec via MultiSourceDriver, register results as DuckDB views,
write a Parquet staging artifact for the model_agent to consume.
"""

from __future__ import annotations

from platform_agent.provisioning.agents._base import (
    AgentContext,
    AgentOutput,
)
from platform_agent.provisioning.models import Artifact


def run(ctx: AgentContext) -> AgentOutput:
    artifacts: list[Artifact] = []
    rows_total = 0
    ctx.emit_progress(
        f"executing {len(ctx.prd.source_pulls)} source pull(s) into DuckDB scratchpad"
    )
    for i, pull in enumerate(ctx.prd.source_pulls, 1):
        # Stub a row count between 50–250 deterministically by SQL length so
        # tests see stable numbers without a DB call.
        row_count = min(250, 50 + (len(pull.sql) % 200))
        rows_total += row_count
        ctx.emit_progress(
            f"pull {i}/{len(ctx.prd.source_pulls)}: {row_count} rows "
            f"from {pull.connection_id[:12]}…"
        )
        a = Artifact(
            kind="source_pull",
            ref=f"{pull.connection_id}:{i}",
            meta={
                "connection_id": pull.connection_id,
                "rows": row_count,
                "max_rows": pull.max_rows,
                "truncated": row_count >= pull.max_rows,
            },
        )
        artifacts.append(a)
        ctx.emit_artifact(a)

    # Staging Parquet artifact (stub path).
    staging = Artifact(
        kind="staging_parquet",
        ref=f"s3://staging/{ctx.run_id}/{ctx.prd.target.table_name}.parquet",
        meta={"rows": rows_total},
    )
    artifacts.append(staging)
    ctx.emit_artifact(staging)
    return AgentOutput(artifacts=artifacts)
