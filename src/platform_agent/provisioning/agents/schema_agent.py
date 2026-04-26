"""schema_agent — extracts source schemas + plans Iceberg DDL (T069, US3).

Promoted from stub to real implementation in Phase 10. For every
SourcePullSpec in the PRD, the agent:

  1. Looks up the source Connection in the WorkspaceRegistry.
  2. Runs `driver.scan_metadata()` (multi-schema aware as of Phase 6 fix).
  3. Records source-side schema counts (tables_scanned, schemas_scanned)
     in the `source_schema` artifact.

Then builds an Iceberg DDL plan for the target Iceberg/Glue table
from the PRD's `entities_proposed` (or, if empty, synthesizes from the
joins' shared keys) using the type-map promoted verbatim from
`patterns/migration-agent/tools/convert_to_iceberg.py`.

Artifact contract is unchanged (`source_schema`, `iceberg_ddl_plan`)
so the existing orchestrator + 7-agent DAG tests continue to pass.

Falls back to a stub when the workspace context isn't reachable
(unit-test isolation) so the agent stays runnable without a live
driver.
"""

from __future__ import annotations

import logging
import re
from typing import Any
from uuid import UUID

from platform_agent.provisioning.agents._base import (
    AgentContext,
    AgentOutput,
)
from platform_agent.provisioning.models import Artifact

logger = logging.getLogger(__name__)


# Type mapping promoted from patterns/migration-agent/tools/
# convert_to_iceberg.py and extended for Postgres / Redshift idioms.
TYPE_MAP: dict[str, str] = {
    "NUMBER": "decimal",
    "DECIMAL": "decimal",
    "NUMERIC": "decimal",
    "INT": "int",
    "INT2": "int",
    "INT4": "int",
    "INT8": "long",
    "INTEGER": "int",
    "BIGINT": "long",
    "SMALLINT": "int",
    "TINYINT": "int",
    "FLOAT": "double",
    "FLOAT4": "float",
    "FLOAT8": "double",
    "DOUBLE": "double",
    "DOUBLE PRECISION": "double",
    "REAL": "float",
    "VARCHAR": "string",
    "CHAR": "string",
    "CHARACTER": "string",
    "STRING": "string",
    "TEXT": "string",
    "BPCHAR": "string",
    "BINARY": "binary",
    "VARBINARY": "binary",
    "BYTEA": "binary",
    "BOOLEAN": "boolean",
    "BOOL": "boolean",
    "DATE": "date",
    "DATETIME": "timestamp",
    "TIME": "time",
    "TIMESTAMP": "timestamp",
    "TIMESTAMP WITHOUT TIME ZONE": "timestamp",
    "TIMESTAMP WITH TIME ZONE": "timestamptz",
    "TIMESTAMP_LTZ": "timestamptz",
    "TIMESTAMP_NTZ": "timestamp",
    "TIMESTAMP_TZ": "timestamptz",
    "VARIANT": "string",
    "OBJECT": "string",
    "ARRAY": "string",
    "UUID": "string",
    "JSON": "string",
    "JSONB": "string",
}


def _map_type(
    raw: str, precision: int | None = None, scale: int | None = None
) -> str:
    base = (raw or "").upper().split("(")[0].strip()
    iceberg = TYPE_MAP.get(base, "string")
    if iceberg == "decimal" and precision is not None:
        return f"decimal({precision}, {scale or 0})"
    return iceberg


def run(ctx: AgentContext) -> AgentOutput:
    artifacts: list[Artifact] = []
    by_connection: dict[str, list[str]] = {}
    for pull in ctx.prd.source_pulls:
        by_connection.setdefault(pull.connection_id, []).append(pull.sql)
    ctx.emit_progress(f"extracting schemas from {len(by_connection)} source(s)")

    workspace_id = _safe_uuid(ctx.workspace_id)
    metadata_by_conn: dict[str, dict[str, Any]] = {}
    if workspace_id is not None:
        for connection_id in by_connection:
            try:
                metadata_by_conn[connection_id] = _scan_real(
                    workspace_id, connection_id
                )
            except Exception as exc:  # noqa: BLE001 — fall back to stub
                logger.debug(
                    "schema_agent: live scan unavailable for %s — using stub: %s",
                    connection_id,
                    exc,
                )
                metadata_by_conn[connection_id] = {}

    for connection_id, pulls in by_connection.items():
        meta = metadata_by_conn.get(connection_id, {})
        ref_tables = sorted({_table_from_sql(s) for s in pulls})
        artifact = Artifact(
            kind="source_schema",
            ref=connection_id,
            meta={
                "connection_id": connection_id,
                "pull_count": len(pulls),
                "tables_referenced": ref_tables,
                "tables_scanned": len(meta.get("tables", [])),
                "schemas_scanned": meta.get("schemas", []),
            },
        )
        artifacts.append(artifact)
        ctx.emit_artifact(artifact)

    target_columns = _target_columns(ctx)
    ddl = _generate_iceberg_ddl(
        glue_database=ctx.prd.target.glue_db,
        table_name=ctx.prd.target.table_name,
        columns=target_columns,
    )
    ddl_artifact = Artifact(
        kind="iceberg_ddl_plan",
        ref=ctx.prd.target.fqn(),
        meta={
            "join_count": len(ctx.prd.joins_identified),
            "target": ctx.prd.target.fqn(),
            "ddl": ddl,
            "column_count": len(target_columns),
            "columns": target_columns,
        },
    )
    artifacts.append(ddl_artifact)
    ctx.emit_artifact(ddl_artifact)
    return AgentOutput(artifacts=artifacts)


# ───── Helpers ─────


def _safe_uuid(raw: str) -> UUID | None:
    try:
        return UUID(raw)
    except ValueError:
        return None


def _scan_real(workspace_id: UUID, connection_id: str) -> dict[str, Any]:
    """Run scan_metadata against the live driver via the workspace registry."""
    from platform_agent.api.routes_workspace_discover import _scan_connection
    from platform_agent.workspace.registry import get_registry

    ws = get_registry().get(workspace_id)
    if ws is None:
        raise RuntimeError("workspace not found")
    conn = ws.find(connection_id)
    if conn is None:
        raise RuntimeError("connection not found")
    return _scan_connection(conn, workspace_id)


def _table_from_sql(sql: str) -> str:
    upper = sql.upper()
    idx = upper.find("FROM ")
    if idx < 0:
        return "?"
    rest = sql[idx + 5 :].strip().split()
    return rest[0] if rest else "?"


def _target_columns(ctx: AgentContext) -> list[dict[str, str]]:
    """Build the target Iceberg table's column list from PRD entities."""
    columns: list[dict[str, str]] = []
    seen: set[str] = set()

    for entity in ctx.prd.entities_proposed:
        for attr in entity.attributes:
            if attr.name in seen:
                continue
            seen.add(attr.name)
            columns.append(
                {
                    "name": attr.name,
                    "iceberg_type": _map_type(attr.data_type),
                    "raw_type": attr.data_type,
                }
            )

    if not columns:
        # Pill-driven PRDs often arrive without entities_proposed; synthesize
        # the target column list from the joins' shared keys.
        join_cols: set[str] = set()
        for join in ctx.prd.joins_identified:
            for left, right in join.keys:
                join_cols.add(_normalize(left))
                join_cols.add(_normalize(right))
        for name in sorted(join_cols):
            columns.append(
                {"name": name, "iceberg_type": "long", "raw_type": "BIGINT"}
            )
        if not columns:
            columns.append(
                {"name": "id", "iceberg_type": "long", "raw_type": "BIGINT"}
            )

    return columns


_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _normalize(name: str) -> str:
    n = name.strip().lower()
    if not _IDENT_RE.match(n):
        n = re.sub(r"[^A-Za-z0-9_]", "_", n)
        if not _IDENT_RE.match(n):
            n = f"col_{abs(hash(name)) % 10000:04d}"
    return n


def _generate_iceberg_ddl(
    *, glue_database: str, table_name: str, columns: list[dict[str, str]]
) -> str:
    """Produce a CREATE TABLE … USING iceberg DDL string."""
    col_defs = ",\n".join(
        f"  {c['name']} {c['iceberg_type']}" for c in columns
    )
    return (
        f"CREATE TABLE IF NOT EXISTS {glue_database}.{table_name} (\n"
        f"{col_defs}\n"
        ")\n"
        "USING iceberg\n"
        "TBLPROPERTIES (\n"
        "  'table_type' = 'ICEBERG',\n"
        "  'format-version' = '2',\n"
        "  'write.format.default' = 'parquet',\n"
        "  'write.parquet.compression-codec' = 'zstd'\n"
        ");"
    )
