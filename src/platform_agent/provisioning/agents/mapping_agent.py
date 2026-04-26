"""mapping_agent — registers the Iceberg table in Glue (T073, US3).

This is the agent that creates the durable artifact: the registered
Iceberg table. v1 stub: writes an Artifact for the registration without
actually calling Glue (the IcebergDriver is wired and works against
real AWS, but a fresh Glue DB + S3 warehouse aren't always available
during demo runs). Real path (deferred): call IcebergDriver.execute_ddl
+ pyiceberg Catalog.create_table().
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from platform_agent.provisioning.agents._base import (
    AgentContext,
    AgentOutput,
)
from platform_agent.provisioning.models import Artifact, IcebergDataProduct, ProductState


def run(ctx: AgentContext) -> AgentOutput:
    fqn = ctx.prd.target.fqn()
    ctx.emit_progress(f"registering Iceberg table {fqn} in Glue")

    artifacts: list[Artifact] = []
    # The registered Iceberg table itself is the headline artifact.
    iceberg_table = Artifact(
        kind="iceberg_table",
        ref=fqn,
        meta={
            "glue_db": ctx.prd.target.glue_db,
            "table_name": ctx.prd.target.table_name,
            "connection_id": ctx.prd.target.connection_id,
        },
    )
    artifacts.append(iceberg_table)
    ctx.emit_artifact(iceberg_table)

    # And a row-count validation receipt (Kimball-style fact registration
    # also produces a row count for downstream attestation).
    row_count_check = Artifact(
        kind="row_count_check",
        ref=f"{fqn}#row-count",
        meta={
            "expected": "TBD (semantic_agent computes from PRD)",
            "actual": 0,
        },
    )
    artifacts.append(row_count_check)
    ctx.emit_artifact(row_count_check)

    # Stash a provisional product on the orchestrator's behalf — delivery_agent
    # will promote it to final after validation crosses the threshold.
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
