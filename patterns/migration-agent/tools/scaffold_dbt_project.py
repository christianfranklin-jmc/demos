"""Tool: Scaffold a dbt project from migrated Snowflake → Iceberg tables.

Generates a complete dbt project with sources pointing to Glue Catalog
(Iceberg tables), staging models (1:1 from source), and skeleton mart
models. Adapts profiles.yml for the target engine (Athena, Redshift, etc.).
"""

from __future__ import annotations

import logging
import os
import textwrap

from strands import tool

logger = logging.getLogger(__name__)


@tool
def scaffold_migration_dbt_project(
    project_name: str,
    source_database: str,
    source_schema: str,
    tables: list[dict],
    target_engine: str = "snowflake",
    output_dir: str = "",
) -> dict:
    """Generate a dbt project for tables migrated from Snowflake to AWS.

    Creates a complete, compilable dbt project with:
    - sources.yml pointing to the migrated tables (Glue Catalog or Snowflake)
    - Staging models (stg_*) with 1:1 mapping and column casting
    - Skeleton mart directory for dimensional models
    - profiles.yml configured for the target engine
    - schema.yml with not_null tests on primary keys

    Args:
        project_name: Name for the dbt project (e.g., "pinnacle_dw").
        source_database: Database name for source definitions.
        source_schema: Schema containing the tables (e.g., "ANALYTICS").
        tables: List of table dicts from extract_snowflake_schema output.
                Each must have: table_name, columns, primary_key, comment.
        target_engine: dbt adapter — "snowflake", "athena", "redshift", "postgres".
        output_dir: Override output directory. Default: dbt_output/<project_name>.
    """
    base_dir = output_dir or os.path.join(os.getcwd(), "dbt_output", project_name)

    dirs = [
        base_dir,
        os.path.join(base_dir, "models", "staging"),
        os.path.join(base_dir, "models", "marts"),
        os.path.join(base_dir, "macros"),
    ]
    for d in dirs:
        os.makedirs(d, exist_ok=True)

    created_files: list[str] = []

    # --- dbt_project.yml ---
    dbt_project = textwrap.dedent(f"""\
        name: '{project_name}'
        version: '1.0.0'
        config-version: 2

        profile: '{project_name}'

        model-paths: ["models"]
        analysis-paths: ["analyses"]
        test-paths: ["tests"]
        seed-paths: ["seeds"]
        macro-paths: ["macros"]
        snapshot-paths: ["snapshots"]

        clean-targets:
          - "target"
          - "dbt_packages"

        models:
          {project_name}:
            staging:
              +materialized: view
            marts:
              +materialized: table
    """)
    _write(base_dir, "dbt_project.yml", dbt_project, created_files)

    # --- profiles.yml (target-engine-specific) ---
    profiles = _build_profiles(project_name, target_engine, source_schema)
    _write(base_dir, "profiles.yml", profiles, created_files)

    # --- packages.yml ---
    packages = textwrap.dedent("""\
        packages:
          - package: dbt-labs/dbt_utils
            version: [">=1.0.0", "<2.0.0"]
    """)
    _write(base_dir, "packages.yml", packages, created_files)

    # --- sources.yml ---
    source_lines = [
        "version: 2",
        "",
        "sources:",
        f"  - name: {source_database.lower()}",
        f"    database: {source_database}",
        f"    schema: {source_schema}",
        "    description: >",
        f"      Tables migrated from Snowflake {source_database}.{source_schema}",
        "    tables:",
    ]
    for tbl in sorted(tables, key=lambda t: t.get("table_name", "")):
        tname = tbl.get("table_name", "")
        comment = tbl.get("comment", "")
        source_lines.append(f"      - name: {tname}")
        if comment:
            escaped = comment.replace("'", "''")
            source_lines.append(f"        description: '{escaped}'")

    sources_yml = "\n".join(source_lines) + "\n"
    _write(
        os.path.join(base_dir, "models"),
        "sources.yml",
        sources_yml,
        created_files,
    )

    # --- Staging models (one per table) ---
    staging_schema_models = []
    for tbl in tables:
        tname = tbl.get("table_name", "")
        columns = tbl.get("columns", [])
        pk = tbl.get("primary_key", [])
        model_name = f"stg_{source_database.lower()}__{tname.lower()}"

        # Build SELECT with explicit column list
        col_refs = []
        for col in columns:
            cname = col.get("column_name", "")
            col_refs.append(f"    {cname.lower()}")

        if col_refs:
            col_list = ",\n".join(col_refs)
            sql = (
                f"-- Staging model for {tname}\n"
                f"-- Source: {source_database}.{source_schema}.{tname}\n\n"
                f"SELECT\n{col_list}\n"
                f"FROM {{{{ source('{source_database.lower()}', '{tname}') }}}}\n"
            )
        else:
            sql = (
                f"SELECT *\n"
                f"FROM {{{{ source('{source_database.lower()}', '{tname}') }}}}\n"
            )

        _write(
            os.path.join(base_dir, "models", "staging"),
            f"{model_name}.sql",
            sql,
            created_files,
        )

        # Schema entry for this staging model
        schema_entry = {"name": model_name, "pk_columns": pk}
        if tbl.get("comment"):
            schema_entry["description"] = tbl["comment"]
        staging_schema_models.append(schema_entry)

    # --- schema.yml for staging models ---
    schema_lines = ["version: 2", "", "models:"]
    for entry in staging_schema_models:
        schema_lines.append(f"  - name: {entry['name']}")
        if entry.get("description"):
            escaped = entry["description"].replace("'", "''")
            schema_lines.append(f"    description: '{escaped}'")
        if entry.get("pk_columns"):
            schema_lines.append("    columns:")
            for pk_col in entry["pk_columns"]:
                schema_lines.append(f"      - name: {pk_col.lower()}")
                schema_lines.append("        tests:")
                schema_lines.append("          - unique")
                schema_lines.append("          - not_null")

    staging_schema = "\n".join(schema_lines) + "\n"
    _write(
        os.path.join(base_dir, "models", "staging"),
        "schema.yml",
        staging_schema,
        created_files,
    )

    # --- Mart skeleton (README placeholder) ---
    mart_readme = (
        "# Mart Models\n\n"
        "Add dimensional models (fct_*, dim_*) here.\n\n"
        "Use `ref('stg_...')` to reference staging models.\n"
    )
    _write(
        os.path.join(base_dir, "models", "marts"),
        "_README.md",
        mart_readme,
        created_files,
    )

    # --- Summary ---
    dim_count = sum(
        1 for t in tables if t.get("table_name", "").upper().startswith("DIM_")
    )
    fact_count = sum(
        1 for t in tables if t.get("table_name", "").upper().startswith("FACT_")
    )

    return {
        "status": "success",
        "project_name": project_name,
        "project_dir": base_dir,
        "target_engine": target_engine,
        "files_created": len(created_files),
        "file_list": created_files,
        "tables": len(tables),
        "staging_models": len(tables),
        "dimensions": dim_count,
        "facts": fact_count,
        "next_steps": [
            f"cd {base_dir}",
            "uv run dbt deps --profiles-dir .",
            "uv run dbt compile --profiles-dir .",
            "uv run dbt run --profiles-dir .",
        ],
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_profiles(
    project_name: str, target_engine: str, schema: str
) -> str:
    """Build profiles.yml for the target engine."""
    if target_engine == "snowflake":
        return textwrap.dedent(f"""\
            {project_name}:
              target: dev
              outputs:
                dev:
                  type: snowflake
                  account: "{{{{ env_var('SF_ACCOUNT') }}}}"
                  user: "{{{{ env_var('SF_USER') }}}}"
                  authenticator: "{{{{ env_var('SF_AUTHENTICATOR', 'externalbrowser') }}}}"
                  role: "{{{{ env_var('SF_ROLE', 'PUBLIC') }}}}"
                  warehouse: "{{{{ env_var('SF_WAREHOUSE') }}}}"
                  database: "{{{{ env_var('SF_DATABASE') }}}}"
                  schema: {schema}
                  threads: 4
        """)
    elif target_engine == "athena":
        return textwrap.dedent(f"""\
            {project_name}:
              target: dev
              outputs:
                dev:
                  type: athena
                  database: "{{{{ env_var('GLUE_DATABASE', 'semantic_lake') }}}}"
                  schema: {schema.lower()}
                  s3_staging_dir: "{{{{ env_var('ATHENA_S3_STAGING') }}}}"
                  region_name: "{{{{ env_var('AWS_REGION', 'us-east-1') }}}}"
                  threads: 4
        """)
    elif target_engine == "redshift":
        return textwrap.dedent(f"""\
            {project_name}:
              target: dev
              outputs:
                dev:
                  type: redshift
                  host: "{{{{ env_var('RS_HOST') }}}}"
                  port: "{{{{ env_var('RS_PORT', '5439') | int }}}}"
                  user: "{{{{ env_var('RS_USER') }}}}"
                  pass: "{{{{ env_var('RS_PASSWORD') }}}}"
                  dbname: "{{{{ env_var('RS_DATABASE', 'dev') }}}}"
                  schema: {schema.lower()}
                  threads: 4
        """)
    else:  # postgres default
        return textwrap.dedent(f"""\
            {project_name}:
              target: dev
              outputs:
                dev:
                  type: postgres
                  host: "{{{{ env_var('DB_HOST') }}}}"
                  port: "{{{{ env_var('DB_PORT', '5432') | int }}}}"
                  user: "{{{{ env_var('DB_USER') }}}}"
                  pass: "{{{{ env_var('DB_PASSWORD') }}}}"
                  dbname: "{{{{ env_var('DB_NAME') }}}}"
                  schema: {schema.lower()}
                  threads: 4
                  sslmode: require
        """)


def _write(directory: str, filename: str, content: str, tracker: list) -> None:
    """Write a file and track it."""
    path = os.path.join(directory, filename)
    with open(path, "w") as f:
        f.write(content)
    tracker.append(path)
