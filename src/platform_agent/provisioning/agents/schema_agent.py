"""schema_agent — extracts source schemas + plans Iceberg DDL (T069, US3).

v1 stub: enumerates the source-pull tables from the PRD and emits a
`source_schema` artifact per source connection. Real path (deferred):
promote `patterns/migration-agent/tools/extract_schema.py` here and
swap this implementation for the live driver call.
"""

from __future__ import annotations

from platform_agent.provisioning.agents._base import (
    AgentContext,
    AgentOutput,
)
from platform_agent.provisioning.models import Artifact


def run(ctx: AgentContext) -> AgentOutput:
    artifacts: list[Artifact] = []
    by_connection: dict[str, list[str]] = {}
    for pull in ctx.prd.source_pulls:
        by_connection.setdefault(pull.connection_id, []).append(pull.sql)
    ctx.emit_progress(f"extracting schemas from {len(by_connection)} source(s)")
    for cid, pulls in by_connection.items():
        artifact = Artifact(
            kind="source_schema",
            ref=cid,
            meta={
                "connection_id": cid,
                "pull_count": len(pulls),
                "tables_referenced": [_table_from_sql(s) for s in pulls],
            },
        )
        artifacts.append(artifact)
        ctx.emit_artifact(artifact)
    # Plan the Iceberg DDL based on declared joins (a stub — full DDL gen
    # lands when patterns/migration-agent/convert_to_iceberg.py is promoted).
    ddl_artifact = Artifact(
        kind="iceberg_ddl_plan",
        ref=f"iceberg.{ctx.prd.target.glue_db}.{ctx.prd.target.table_name}",
        meta={
            "join_count": len(ctx.prd.joins_identified),
            "target": ctx.prd.target.fqn(),
        },
    )
    artifacts.append(ddl_artifact)
    ctx.emit_artifact(ddl_artifact)
    return AgentOutput(artifacts=artifacts)


def _table_from_sql(sql: str) -> str:
    upper = sql.upper()
    idx = upper.find("FROM ")
    if idx < 0:
        return "?"
    rest = sql[idx + 5 :].strip().split()
    return rest[0] if rest else "?"
