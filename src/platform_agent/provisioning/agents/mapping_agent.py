"""mapping_agent — registers the Iceberg table in Glue (T073, US3).

Promoted from stub to real implementation in Phase 10. The agent:

  1. Reads the upstream `iceberg_ddl_plan` artifact produced by
     schema_agent (target column list + Iceberg type map).
  2. Looks up the target IcebergDriver via the workspace registry.
  3. Attempts a real `pyiceberg.Catalog.create_table()` against the
     driver's Glue catalog. On any error (no catalog wired, no S3
     bucket reachable, table already exists), falls back to recording
     the planned DDL only — the run still completes with a
     `provisional` product so delivery_agent + the rest of the DAG
     proceed. Tests + offline demos depend on this fallback.
  4. Emits the same artifact kinds the stub did
     (`iceberg_table`, `row_count_check`, `iceberg_data_product`)
     so the existing 7-agent DAG tests keep passing.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from platform_agent.provisioning.agents._base import (
    AgentContext,
    AgentOutput,
)
from platform_agent.provisioning.models import (
    AgentId,
    Artifact,
    IcebergDataProduct,
    ProductState,
)

logger = logging.getLogger(__name__)


def run(ctx: AgentContext) -> AgentOutput:
    fqn = ctx.prd.target.fqn()
    ctx.emit_progress(f"registering Iceberg table {fqn} in Glue")

    # Pull schema_agent's DDL plan (always present in the live DAG; only
    # missing in the rare unit-test that bypasses the orchestrator).
    schema_artifacts = ctx.upstream_artifacts.get(AgentId.SCHEMA, [])
    ddl_plan = next(
        (a for a in schema_artifacts if a.kind == "iceberg_ddl_plan"), None
    )
    columns: list[dict[str, str]] = (
        ddl_plan.meta.get("columns", []) if ddl_plan else []
    )
    ddl: str = ddl_plan.meta.get("ddl", "") if ddl_plan else ""

    register_status, register_message = _try_real_register(ctx, columns)

    artifacts: list[Artifact] = []
    iceberg_table = Artifact(
        kind="iceberg_table",
        ref=fqn,
        meta={
            "glue_db": ctx.prd.target.glue_db,
            "table_name": ctx.prd.target.table_name,
            "connection_id": ctx.prd.target.connection_id,
            "register_status": register_status,
            "register_message": register_message,
            "column_count": len(columns),
            "ddl_preview": ddl[:240] + ("…" if len(ddl) > 240 else ""),
        },
    )
    artifacts.append(iceberg_table)
    ctx.emit_artifact(iceberg_table)

    row_count_check = Artifact(
        kind="row_count_check",
        ref=f"{fqn}#row-count",
        meta={
            "expected": "TBD (semantic_agent computes from PRD)",
            "actual": 0,
            "register_status": register_status,
        },
    )
    artifacts.append(row_count_check)
    ctx.emit_artifact(row_count_check)

    product = IcebergDataProduct(
        product_id=str(uuid4()),
        connection_id=ctx.prd.target.connection_id,
        table_name=fqn,
        state=ProductState.PROVISIONAL,
        ttyd_exposed=False,
        created_by_run_id=ctx.run_id,
        prd_snapshot=ctx.prd,
        validation_pass_rate=0.0,
        created_at=datetime.now(tz=UTC),
        updated_at=datetime.now(tz=UTC),
    )
    product_ref = Artifact(
        kind="iceberg_data_product",
        ref=product.product_id,
        meta=product.model_dump(mode="json"),
    )
    artifacts.append(product_ref)
    ctx.emit_artifact(product_ref)
    return AgentOutput(artifacts=artifacts)


def _try_real_register(
    ctx: AgentContext, columns: list[dict[str, str]]
) -> tuple[str, str]:
    """Attempt a real pyiceberg create_table; return (status, message).

    Status values: `created`, `already_exists`, `planned_only` (offline
    fallback), `error`. The DAG continues regardless of the outcome —
    delivery_agent will mark the product final/provisional based on
    validation, not on register success.
    """
    workspace_id = _safe_uuid(ctx.workspace_id)
    if workspace_id is None or not columns:
        return "planned_only", "no live workspace context (test path)"

    try:
        from platform_agent.api.routes_workspace import get_credentials
        from platform_agent.drivers.iceberg import IcebergDriver
        from platform_agent.workspace.models import DriverType
        from platform_agent.workspace.registry import get_registry

        ws = get_registry().get(workspace_id)
        if ws is None:
            return "planned_only", "workspace not in registry"
        target_conn = ws.find(ctx.prd.target.connection_id)
        if target_conn is None or target_conn.driver_type != DriverType.ICEBERG:
            return "planned_only", "target connection is not an Iceberg driver"
        creds = get_credentials(workspace_id, target_conn.connection_id) or {}
        if not creds.get("warehouse_s3_uri"):
            return (
                "planned_only",
                "no warehouse_s3_uri in credentials — DDL plan recorded only",
            )

        driver = IcebergDriver(
            glue_database=target_conn.scope,
            warehouse_s3_uri=creds["warehouse_s3_uri"],
            region=creds.get("region", "us-east-1"),
        )
        driver.connect()
        try:
            return _create_iceberg_table(driver, ctx, columns)
        finally:
            driver.close()
    except Exception as exc:  # noqa: BLE001 — never fail the DAG on a register error
        logger.warning("mapping_agent: real register failed — %s", exc)
        return "error", f"{type(exc).__name__}: {exc}"


def _create_iceberg_table(
    driver: Any, ctx: AgentContext, columns: list[dict[str, str]]
) -> tuple[str, str]:
    """Call pyiceberg.Catalog.create_table() with the planned schema."""
    try:
        from pyiceberg.exceptions import TableAlreadyExistsError
        from pyiceberg.schema import Schema
        from pyiceberg.types import (
            BinaryType,
            BooleanType,
            DateType,
            DoubleType,
            FloatType,
            IntegerType,
            LongType,
            NestedField,
            StringType,
            TimestampType,
            TimestamptzType,
            TimeType,
        )
    except ImportError as exc:
        return "planned_only", f"pyiceberg import failed: {exc}"

    iceberg_to_type = {
        "int": IntegerType(),
        "long": LongType(),
        "float": FloatType(),
        "double": DoubleType(),
        "boolean": BooleanType(),
        "string": StringType(),
        "binary": BinaryType(),
        "date": DateType(),
        "time": TimeType(),
        "timestamp": TimestampType(),
        "timestamptz": TimestamptzType(),
    }

    fields: list[Any] = []
    for i, col in enumerate(columns, start=1):
        base = col["iceberg_type"].split("(")[0]
        iceberg_type = iceberg_to_type.get(base, StringType())
        fields.append(
            NestedField(
                field_id=i,
                name=col["name"],
                field_type=iceberg_type,
                required=False,
            )
        )

    schema = Schema(*fields)
    catalog = getattr(driver, "_catalog", None)
    if catalog is None:
        return "planned_only", "driver has no live pyiceberg catalog"

    table_id = f"{ctx.prd.target.glue_db}.{ctx.prd.target.table_name}"
    try:
        catalog.create_table(identifier=table_id, schema=schema)
        return "created", f"created {table_id} with {len(fields)} field(s)"
    except TableAlreadyExistsError:
        return "already_exists", f"{table_id} already registered"


def _safe_uuid(raw: str) -> UUID | None:
    try:
        return UUID(raw)
    except ValueError:
        return None
