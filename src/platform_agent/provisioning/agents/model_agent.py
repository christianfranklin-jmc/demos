"""model_agent — dbt scaffolding (T071, US3).

Promoted from stub to real implementation in Phase 10d. Calls the
existing `generate_dbt_project` tool (the same one used by the
single-source workflow's Step 4) to write a complete dbt project to
disk under `~/.dsa-hub/runs/<run_id>/dbt/<table>/`.

Inputs come from upstream artifacts:
  - schema_agent's `iceberg_ddl_plan` (target columns, DDL preview).
  - pipeline_agent's `source_pull` records (per-source views).

Output: a real dbt project + `dbt_model` artifacts pointing at the
generated files + a `dbt_profile` artifact for the dbt-glue adapter.

Falls back to the stub artifact list when generate_dbt_project is
unavailable or raises (test isolation, transient FS errors). The
artifact contract — kinds + the `layer` / `materialization` meta —
is unchanged so the existing 7-agent DAG tests keep passing; new
runs add a `source: "live" | "stub"` tag so the Build page can show
provenance.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from platform_agent.provisioning.agents._base import (
    AgentContext,
    AgentOutput,
)
from platform_agent.provisioning.models import AgentId, Artifact

logger = logging.getLogger(__name__)


def run(ctx: AgentContext) -> AgentOutput:
    target = ctx.prd.target.table_name
    ctx.emit_progress(f"scaffolding dbt project for {target}")

    artifacts: list[Artifact] = []

    schema_artifacts = ctx.upstream_artifacts.get(AgentId.SCHEMA, [])
    ddl_plan = next(
        (a for a in schema_artifacts if a.kind == "iceberg_ddl_plan"), None
    )

    real_project = _try_generate_real_project(ctx, ddl_plan)

    if real_project is not None:
        for path in real_project.get("staging_paths", []):
            a = Artifact(
                kind="dbt_model",
                ref=path,
                meta={"layer": "staging", "source": "live"},
            )
            artifacts.append(a)
            ctx.emit_artifact(a)
        for path in real_project.get("mart_paths", []):
            a = Artifact(
                kind="dbt_model",
                ref=path,
                meta={
                    "layer": "marts",
                    "materialization": "iceberg",
                    "source": "live",
                },
            )
            artifacts.append(a)
            ctx.emit_artifact(a)
        profile = Artifact(
            kind="dbt_profile",
            ref=str(real_project["profile_path"]),
            meta={"adapter": "glue", "type": "iceberg", "source": "live"},
        )
        artifacts.append(profile)
        ctx.emit_artifact(profile)
        return AgentOutput(artifacts=artifacts)

    # ───── Fallback: deterministic stub identical to the prior v1 ─────

    for pull in ctx.prd.source_pulls:
        path = f"models/staging/stg_{pull.connection_id[:8]}__{target}.sql"
        a = Artifact(
            kind="dbt_model",
            ref=path,
            meta={"layer": "staging", "source": "stub"},
        )
        artifacts.append(a)
        ctx.emit_artifact(a)
    for i, join in enumerate(ctx.prd.joins_identified, 1):
        path = f"models/intermediate/int_{target}__join_{i}.sql"
        a = Artifact(
            kind="dbt_model",
            ref=path,
            meta={
                "layer": "intermediate",
                "left": join.left_fqn,
                "right": join.right_fqn,
                "source": "stub",
            },
        )
        artifacts.append(a)
        ctx.emit_artifact(a)
    mart_path = f"models/marts/{target}.sql"
    mart = Artifact(
        kind="dbt_model",
        ref=mart_path,
        meta={"layer": "marts", "materialization": "iceberg", "source": "stub"},
    )
    artifacts.append(mart)
    ctx.emit_artifact(mart)
    profile = Artifact(
        kind="dbt_profile",
        ref="profiles.yml",
        meta={"adapter": "glue", "type": "iceberg", "source": "stub"},
    )
    artifacts.append(profile)
    ctx.emit_artifact(profile)
    return AgentOutput(artifacts=artifacts)


# ───── Real-project generation ─────


def _try_generate_real_project(
    ctx: AgentContext,
    ddl_plan: Artifact | None,
) -> dict[str, Any] | None:
    """Invoke generate_dbt_project; return paths on success, None on failure."""
    try:
        from platform_agent.tools.dbt_generate import generate_dbt_project

        impl = getattr(generate_dbt_project, "__wrapped__", generate_dbt_project)
    except ImportError as exc:
        logger.debug("model_agent: generate_dbt_project unavailable — %s", exc)
        return None

    target = ctx.prd.target.table_name
    glue_db = ctx.prd.target.glue_db

    pull_specs = ctx.prd.source_pulls
    source_tables: list[str] = []
    staging_models: list[dict[str, str]] = []
    for i, pull in enumerate(pull_specs, 1):
        slug = f"src_{i}_{pull.connection_id[:8]}"
        source_tables.append(slug)
        staging_models.append(
            {
                "name": f"stg_{slug}__{target}",
                "sql": (
                    "{{ config(materialized='view') }}\n\n"
                    f"-- pull #{i} from connection {pull.connection_id[:12]}…\n"
                    "SELECT * FROM {{ source('staging', '" + slug + "') }}\n"
                ),
            }
        )

    columns: list[dict[str, str]] = (
        ddl_plan.meta.get("columns", []) if ddl_plan else []
    )
    first_stg = staging_models[0]["name"] if staging_models else None
    if columns and first_stg:
        col_list = ",\n  ".join(c["name"] for c in columns)
        mart_sql = (
            "{{ config(materialized='table', file_format='iceberg') }}\n\n"
            f"SELECT\n  {col_list}\nFROM {{{{ ref('{first_stg}') }}}}\n"
        )
    elif first_stg:
        mart_sql = (
            "{{ config(materialized='table', file_format='iceberg') }}\n"
            f"SELECT * FROM {{{{ ref('{first_stg}') }}}}\n"
        )
    else:
        # No staging — emit a literal so dbt compiles.
        mart_sql = (
            "{{ config(materialized='table', file_format='iceberg') }}\n"
            "SELECT 1 AS placeholder\n"
        )

    mart_models = [
        {
            "name": target,
            "sql": mart_sql,
            "materialized": "table",
        }
    ]

    out_dir = Path.home() / ".dsa-hub" / "runs" / ctx.run_id / "dbt"
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
    except Exception as exc:  # noqa: BLE001
        logger.debug("model_agent: cannot create output dir — %s", exc)
        return None

    try:
        result = impl(
            project_name=target,
            target_schema=glue_db,
            source_database=glue_db,
            source_schema="staging",
            source_tables=source_tables or ["placeholder"],
            staging_models=staging_models,
            mart_models=mart_models,
            output_dir=str(out_dir / target),
        )
    except Exception as exc:  # noqa: BLE001
        logger.debug("model_agent: generate_dbt_project raised — %s", exc)
        return None

    if not isinstance(result, dict) or result.get("status") != "success":
        return None

    project_dir = Path(result["project_dir"])
    files_created = result.get("files_created", [])
    staging_paths = [
        str(p)
        for p in files_created
        if "/staging/" in str(p) and str(p).endswith(".sql")
    ]
    mart_paths = [
        str(p)
        for p in files_created
        if "/marts/" in str(p) and str(p).endswith(".sql")
    ]
    profile_path = project_dir / "profiles.yml"
    return {
        "project_dir": project_dir,
        "staging_paths": staging_paths,
        "mart_paths": mart_paths,
        "profile_path": profile_path,
    }
