"""Tool: Generate a dbt project from a dimensional model design."""

from __future__ import annotations

import os
import textwrap

from strands import tool


@tool
def generate_dbt_project(
    project_name: str,
    target_schema: str,
    source_database: str,
    source_schema: str,
    source_tables: list[str],
    staging_models: list[dict],
    mart_models: list[dict],
    output_dir: str = "",
) -> dict:
    """Generate a complete dbt project with sources, staging, and mart models.

    Call this after the user has approved a dimensional model design. Produces
    a dbt project that can be compiled with `dbt compile` and run with `dbt run`.

    Args:
        project_name: Name for the dbt project (e.g., "northwinds_dw").
        target_schema: Schema where mart models will be materialized (e.g., "northwinds_dw").
        source_database: Database name for source definitions.
        source_schema: Schema containing raw source tables (e.g., "public").
        source_tables: List of source table names to include.
        staging_models: List of staging model definitions. Each dict has:
            - name: Model filename without .sql (e.g., "stg_northwinds__orders")
            - sql: The complete SQL for the model using source() refs
        mart_models: List of mart model definitions. Each dict has:
            - name: Model filename without .sql (e.g., "fct_order_lines")
            - sql: The complete SQL for the model using ref() refs
            - materialized: Optional materialization strategy ("table" or "view")
    """
    base_dir = output_dir or os.path.join(os.getcwd(), "dbt_output", project_name)

    # Create directory structure
    dirs = [
        base_dir,
        os.path.join(base_dir, "models", "staging"),
        os.path.join(base_dir, "models", "marts"),
    ]
    for d in dirs:
        os.makedirs(d, exist_ok=True)

    created_files = []

    # 1. dbt_project.yml
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
              +schema: {target_schema}
    """)
    _write_file(base_dir, "dbt_project.yml", dbt_project, created_files)

    # 2. profiles.yml (local development profile)
    profiles = textwrap.dedent(f"""\
        {project_name}:
          target: dev
          outputs:
            dev:
              type: postgres
              host: "{{{{ env_var('DBT_HOST') }}}}"
              port: "{{{{ env_var('DBT_PORT', '5432') | int }}}}"
              user: "{{{{ env_var('DBT_USER') }}}}"
              pass: "{{{{ env_var('DBT_PASSWORD') }}}}"
              dbname: "{{{{ env_var('DBT_DBNAME') }}}}"
              schema: {source_schema}
              threads: 4
              sslmode: require
    """)
    _write_file(base_dir, "profiles.yml", profiles, created_files)

    # 2b. packages.yml (dbt_utils for surrogate keys, etc.)
    packages = textwrap.dedent("""\
        packages:
          - package: dbt-labs/dbt_utils
            version: [">=1.0.0", "<2.0.0"]
    """)
    _write_file(base_dir, "packages.yml", packages, created_files)

    # 3. sources.yml
    source_lines = ["version: 2", "", "sources:", f"  - name: {source_database}",
                    f"    database: {source_database}", f"    schema: {source_schema}",
                    "    tables:"]
    for t in sorted(source_tables):
        source_lines.append(f"      - name: {t}")
    sources_yml = "\n".join(source_lines) + "\n"
    _write_file(os.path.join(base_dir, "models"), "sources.yml", sources_yml, created_files)

    # 4. Staging models
    for model in staging_models:
        _write_file(
            os.path.join(base_dir, "models", "staging"),
            f"{model['name']}.sql",
            model["sql"],
            created_files,
        )

    # 5. Mart models (facts + dimensions)
    for model in mart_models:
        materialized = model.get("materialized", "table")
        header = f"{{{{ config(materialized='{materialized}') }}}}\n\n"
        _write_file(
            os.path.join(base_dir, "models", "marts"),
            f"{model['name']}.sql",
            header + model["sql"],
            created_files,
        )

    # 6. schema.yml for marts (basic documentation + PK tests)
    mart_entries = []
    for model in mart_models:
        name = model["name"]
        # Infer PK column from naming convention
        if name.startswith("dim_"):
            pk_col = f"{name}_key"
        elif name.startswith("fct_"):
            pk_col = f"{name}_key"
        else:
            pk_col = "id"
        mart_entries.append(textwrap.dedent(f"""\
          - name: {name}
            columns:
              - name: {pk_col}
                tests:
                  - unique
                  - not_null"""))

    schema_yml = "version: 2\n\nmodels:\n" + "\n".join(mart_entries) + "\n"
    _write_file(os.path.join(base_dir, "models", "marts"), "schema.yml", schema_yml, created_files)

    return {
        "status": "success",
        "project_dir": base_dir,
        "files_created": created_files,
        "next_steps": [
            f"Set environment variables: DBT_HOST, DBT_PORT, DBT_USER, DBT_PASSWORD, DBT_DBNAME",
            f"cd {base_dir} && dbt deps --profiles-dir .",
            f"cd {base_dir} && dbt compile --profiles-dir .",
            f"cd {base_dir} && dbt run --profiles-dir .",
        ],
    }


def _write_file(directory: str, filename: str, content: str, tracker: list) -> None:
    """Write a file and track it."""
    path = os.path.join(directory, filename)
    with open(path, "w") as f:
        f.write(content)
    tracker.append(path)
