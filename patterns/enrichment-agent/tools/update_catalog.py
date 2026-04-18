"""Tool: Update Glue Data Catalog and Snowflake with enriched descriptions.

Writes generated descriptions back to the source catalog (Glue or Snowflake)
so downstream consumers see business-quality metadata.
"""

from __future__ import annotations

import logging

from strands import tool

logger = logging.getLogger(__name__)


@tool
def update_catalog_descriptions(
    source_id: str,
    table_descriptions: list[dict],
    target: str = "snowflake",
    glue_database: str = "",
) -> dict:
    """Write enriched descriptions to the data catalog.

    Updates table and column comments in either Snowflake (via ALTER TABLE/COLUMN)
    or AWS Glue Data Catalog (via UpdateTable API).

    Args:
        source_id: The source identifier from connect_to_database.
        table_descriptions: List of dicts from generate_descriptions output.
            Each must have: table_name, generated_description, columns[].
        target: Where to write — "snowflake" or "glue".
        glue_database: Glue database name (required if target="glue").
    """
    if target == "snowflake":
        return _update_snowflake(source_id, table_descriptions)
    elif target == "glue":
        return _update_glue(table_descriptions, glue_database)
    else:
        return {"error": f"Unknown target: {target}. Use 'snowflake' or 'glue'."}


def _update_snowflake(source_id: str, table_descriptions: list[dict]) -> dict:
    """Update Snowflake table/column comments via ALTER statements."""
    import sys
    sys.path.insert(0, "/app/src")
    from platform_agent.drivers import get_driver

    driver = get_driver(source_id)
    updated_tables = 0
    updated_columns = 0
    errors = []

    for tbl in table_descriptions:
        tname = tbl.get("table_name", "")
        table_desc = tbl.get("generated_description", "")

        # Update table comment
        if table_desc:
            escaped = table_desc.replace("'", "''")
            try:
                driver.execute_ddl(
                    f"ALTER TABLE \"{tname}\" SET COMMENT = '{escaped}'"
                )
                updated_tables += 1
            except Exception as e:
                errors.append(f"table {tname}: {e}")

        # Update column comments
        for col in tbl.get("columns", []):
            cname = col.get("column_name", "")
            col_desc = col.get("generated_description", "")
            if col_desc and not col.get("existing_comment"):
                escaped = col_desc.replace("'", "''")
                try:
                    driver.execute_ddl(
                        f"ALTER TABLE \"{tname}\" ALTER COLUMN "
                        f"\"{cname}\" SET COMMENT '{escaped}'"
                    )
                    updated_columns += 1
                except Exception as e:
                    errors.append(f"column {tname}.{cname}: {e}")

    return {
        "target": "snowflake",
        "tables_updated": updated_tables,
        "columns_updated": updated_columns,
        "errors": errors[:10],
        "status": "success" if not errors else "partial",
    }


def _update_glue(table_descriptions: list[dict], glue_database: str) -> dict:
    """Update Glue Data Catalog descriptions via UpdateTable API."""
    import os

    try:
        import boto3
    except ImportError:
        return {"error": "boto3 not available for Glue updates"}

    glue = boto3.client(
        "glue",
        region_name=os.environ.get("AWS_REGION", "us-east-1"),
    )
    updated = 0
    errors = []

    for tbl in table_descriptions:
        tname = tbl.get("table_name", "").lower()
        table_desc = tbl.get("generated_description", "")

        try:
            # Get existing table definition
            existing = glue.get_table(
                DatabaseName=glue_database, Name=tname
            )
            table_input = existing["Table"]

            # Remove read-only fields
            for key in [
                "DatabaseName", "CreateTime", "UpdateTime",
                "CreatedBy", "IsRegisteredWithLakeFormation",
                "CatalogId", "VersionId",
            ]:
                table_input.pop(key, None)

            # Update description
            if table_desc:
                table_input["Description"] = table_desc

            # Update column descriptions
            cols = table_input.get("StorageDescriptor", {}).get("Columns", [])
            col_desc_map = {
                c["column_name"].lower(): c.get("generated_description", "")
                for c in tbl.get("columns", [])
            }
            for col in cols:
                desc = col_desc_map.get(col["Name"].lower(), "")
                if desc and not col.get("Comment"):
                    col["Comment"] = desc

            glue.update_table(
                DatabaseName=glue_database, TableInput=table_input
            )
            updated += 1
        except Exception as e:
            errors.append(f"{tname}: {e}")

    return {
        "target": "glue",
        "glue_database": glue_database,
        "tables_updated": updated,
        "errors": errors[:10],
        "status": "success" if not errors else "partial",
    }


@tool
def build_synonym_map(
    source_id: str,
    tables: list[str] | None = None,
) -> dict:
    """Generate natural language synonyms for business metrics and columns.

    Creates a synonym map that helps the Query Agent understand different
    ways users might refer to the same metric or dimension.

    Args:
        source_id: The source identifier from connect_to_database.
        tables: Optional list of tables. If empty, generates for all.
    """
    import sys
    sys.path.insert(0, "/app/src")
    from platform_agent.drivers import get_driver

    driver = get_driver(source_id)
    metadata = driver.scan_metadata()

    all_tables = metadata.get("tables", [])
    if tables:
        all_tables = [t for t in all_tables if t.get("table_name") in tables]

    synonyms: dict[str, list[str]] = {}

    for tbl in all_tables:
        tname = tbl.get("table_name", "")
        # Table synonyms
        clean = tname.replace("FACT_", "").replace("DIM_", "").replace("_", " ")
        synonyms[tname] = [clean.lower(), clean.title()]

        for col in tbl.get("columns", []):
            cname = col.get("column_name", "")
            full_key = f"{tname}.{cname}"
            clean_col = cname.replace("_", " ").lower()

            col_synonyms = [clean_col]

            # Common business synonyms
            upper = cname.upper()
            if "REVENUE" in upper:
                col_synonyms.extend(["income", "sales", "earnings"])
            elif "EXPENSE" in upper or "COST" in upper:
                col_synonyms.extend(["spending", "expenditure", "costs"])
            elif "AUM" in upper:
                col_synonyms.extend([
                    "assets under management", "managed assets", "total assets",
                ])
            elif "BUDGET" in upper:
                col_synonyms.extend(["planned", "forecast", "target"])
            elif "VARIANCE" in upper:
                col_synonyms.extend(["difference", "delta", "gap"])
            elif "CLIENT" in upper or "CUSTOMER" in upper:
                col_synonyms.extend(["client", "customer", "account"])

            synonyms[full_key] = col_synonyms

    return {
        "source_id": source_id,
        "synonym_entries": len(synonyms),
        "synonyms": synonyms,
    }
