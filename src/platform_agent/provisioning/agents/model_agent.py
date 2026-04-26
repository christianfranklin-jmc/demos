"""model_agent — dbt scaffolding (T071, US3).

v1 stub: emits the dbt model paths the project would produce
(staging + intermediate + marts per Kimball / Addendum B). Real path
(deferred): promote `patterns/migration-agent/tools/scaffold_dbt_project.py`
and target dbt-glue for Iceberg materialization.
"""

from __future__ import annotations

from platform_agent.provisioning.agents._base import (
    AgentContext,
    AgentOutput,
)
from platform_agent.provisioning.models import Artifact


def run(ctx: AgentContext) -> AgentOutput:
    target = ctx.prd.target.table_name
    ctx.emit_progress(f"scaffolding dbt project for {target}")

    artifacts: list[Artifact] = []
    # Staging: one per source connection.
    for pull in ctx.prd.source_pulls:
        path = f"models/staging/stg_{pull.connection_id[:8]}__{target}.sql"
        a = Artifact(kind="dbt_model", ref=path, meta={"layer": "staging"})
        artifacts.append(a)
        ctx.emit_artifact(a)

    # Intermediate: one join model per declared join.
    for i, join in enumerate(ctx.prd.joins_identified, 1):
        path = f"models/intermediate/int_{target}__join_{i}.sql"
        a = Artifact(
            kind="dbt_model",
            ref=path,
            meta={
                "layer": "intermediate",
                "left": join.left_fqn,
                "right": join.right_fqn,
            },
        )
        artifacts.append(a)
        ctx.emit_artifact(a)

    # Mart fact.
    mart_path = f"models/marts/{target}.sql"
    mart = Artifact(
        kind="dbt_model",
        ref=mart_path,
        meta={"layer": "marts", "materialization": "iceberg"},
    )
    artifacts.append(mart)
    ctx.emit_artifact(mart)

    profile = Artifact(
        kind="dbt_profile",
        ref="profiles.yml",
        meta={"adapter": "glue", "type": "iceberg"},
    )
    artifacts.append(profile)
    ctx.emit_artifact(profile)
    return AgentOutput(artifacts=artifacts)
