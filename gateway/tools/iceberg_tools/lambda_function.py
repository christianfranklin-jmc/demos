"""Gateway Lambda handler for Apache Iceberg operations.

Provides tools for converting Snowflake schemas to Iceberg DDL,
triggering Glue ETL exports, and registering tables in Glue Catalog.

Tool names follow MCP convention: {target}___{tool_name}
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)


# ---------------------------------------------------------------------------
# Snowflake → Iceberg type mapping
# ---------------------------------------------------------------------------

SF_TO_ICEBERG_TYPES: dict[str, str] = {
    "NUMBER": "decimal",
    "DECIMAL": "decimal",
    "NUMERIC": "decimal",
    "INT": "int",
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
    "BINARY": "binary",
    "VARBINARY": "binary",
    "BOOLEAN": "boolean",
    "DATE": "date",
    "DATETIME": "timestamp",
    "TIME": "time",
    "TIMESTAMP": "timestamp",
    "TIMESTAMP_LTZ": "timestamptz",
    "TIMESTAMP_NTZ": "timestamp",
    "TIMESTAMP_TZ": "timestamptz",
    "VARIANT": "string",
    "OBJECT": "string",
    "ARRAY": "string",
}


def _map_sf_type(sf_type: str, precision: int | None = None, scale: int | None = None) -> str:
    """Map a Snowflake data type to an Iceberg type."""
    base = sf_type.upper().split("(")[0].strip()
    iceberg_type = SF_TO_ICEBERG_TYPES.get(base, "string")
    if iceberg_type == "decimal" and precision is not None:
        return f"decimal({precision}, {scale or 0})"
    return iceberg_type


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------


def _tool_convert_to_iceberg(**kwargs: Any) -> dict:
    """Generate Iceberg CREATE TABLE DDL from a Snowflake table spec.

    Accepts a table_spec dict with table_name, columns, clustering_key.
    Generates Iceberg-compatible DDL with partition transforms derived
    from Snowflake clustering keys.
    """
    table_spec = kwargs.get("table_spec", {})
    if isinstance(table_spec, str):
        table_spec = json.loads(table_spec)

    table_name = table_spec.get("table_name", "unknown")
    columns = table_spec.get("columns", [])
    clustering_key = table_spec.get("clustering_key", "")
    s3_location = kwargs.get("s3_location", f"s3://data-lake/iceberg/{table_name}/")

    # Build column definitions
    col_defs = []
    for col in columns:
        col_name = col.get("column_name", "").lower()
        sf_type = col.get("data_type", "VARCHAR")
        precision = col.get("numeric_precision")
        scale = col.get("numeric_scale")
        iceberg_type = _map_sf_type(sf_type, precision, scale)
        nullable = "NOT NULL" if col.get("is_nullable", "YES") == "NO" else ""
        comment = col.get("comment", "")
        comment_clause = f" COMMENT '{comment}'" if comment else ""
        col_defs.append(f"  {col_name} {iceberg_type} {nullable}{comment_clause}".rstrip())

    columns_sql = ",\n".join(col_defs)

    # Partition spec from clustering key
    partition_clause = ""
    if clustering_key:
        # Parse clustering key: LINEAR(col1, col2) → PARTITIONED BY (col1, col2)
        key_str = clustering_key.strip()
        if key_str.startswith("LINEAR("):
            key_str = key_str[7:-1]
        partition_cols = [c.strip().lower() for c in key_str.split(",") if c.strip()]
        if partition_cols:
            partition_clause = f"\nPARTITIONED BY ({', '.join(partition_cols)})"

    ddl = f"""CREATE TABLE IF NOT EXISTS {table_name.lower()} (
{columns_sql}
)
USING ICEBERG{partition_clause}
LOCATION '{s3_location}'
TBLPROPERTIES (
  'table_type' = 'ICEBERG',
  'format' = 'parquet',
  'write.format.default' = 'parquet'
);"""

    return {
        "table_name": table_name,
        "ddl": ddl,
        "column_count": len(col_defs),
        "has_partitioning": bool(partition_clause),
        "s3_location": s3_location,
    }


def _tool_export_data(**kwargs: Any) -> dict:
    """Trigger a Glue ETL job to export Snowflake data to S3 as Iceberg/Parquet.

    This creates or starts a Glue job that reads from Snowflake and writes
    to the target S3 location in Iceberg format.
    """
    table_name = kwargs.get("table", "")
    s3_prefix = kwargs.get("s3_prefix", "s3://data-lake/iceberg/")
    glue_job_name = kwargs.get("glue_job_name", f"export-{table_name}")

    if not table_name:
        raise ValueError("table parameter is required")

    glue = boto3.client("glue", region_name=os.environ.get("AWS_REGION", "us-east-1"))

    # Start the Glue job (assumes job already exists via Terraform)
    try:
        response = glue.start_job_run(
            JobName=glue_job_name,
            Arguments={
                "--source_table": table_name,
                "--target_s3_path": f"{s3_prefix}{table_name}/",
                "--source_database": os.environ.get("SF_DATABASE", ""),
                "--source_schema": os.environ.get("SF_SCHEMA", "PUBLIC"),
            },
        )
        return {
            "status": "started",
            "table": table_name,
            "glue_job_name": glue_job_name,
            "job_run_id": response["JobRunId"],
            "target": f"{s3_prefix}{table_name}/",
        }
    except glue.exceptions.EntityNotFoundException:
        return {
            "status": "error",
            "error": f"Glue job '{glue_job_name}' not found. Deploy via Terraform first.",
        }


def _tool_register_glue_catalog(**kwargs: Any) -> dict:
    """Register an Iceberg table in the AWS Glue Data Catalog.

    Creates a Glue table entry pointing to the S3 Iceberg location
    with the appropriate table properties for Iceberg format.
    """
    table_spec = kwargs.get("table_spec", {})
    if isinstance(table_spec, str):
        table_spec = json.loads(table_spec)

    table_name = table_spec.get("table_name", "").lower()
    columns = table_spec.get("columns", [])
    s3_location = kwargs.get("s3_location", f"s3://data-lake/iceberg/{table_name}/")
    glue_database = kwargs.get("glue_database", os.environ.get("GLUE_DATABASE", "semantic_lake"))

    if not table_name:
        raise ValueError("table_spec.table_name is required")

    glue = boto3.client("glue", region_name=os.environ.get("AWS_REGION", "us-east-1"))

    # Build Glue column definitions
    glue_columns = []
    for col in columns:
        col_name = col.get("column_name", "").lower()
        sf_type = col.get("data_type", "VARCHAR")
        iceberg_type = _map_sf_type(
            sf_type, col.get("numeric_precision"), col.get("numeric_scale"),
        )
        glue_columns.append({
            "Name": col_name,
            "Type": iceberg_type,
            "Comment": col.get("comment", ""),
        })

    table_input = {
        "Name": table_name,
        "StorageDescriptor": {
            "Columns": glue_columns,
            "Location": s3_location,
            "InputFormat": "org.apache.iceberg.mr.hive.HiveIcebergInputFormat",
            "OutputFormat": "org.apache.iceberg.mr.hive.HiveIcebergOutputFormat",
            "SerdeInfo": {
                "SerializationLibrary": "org.apache.iceberg.mr.hive.HiveIcebergSerDe",
            },
        },
        "TableType": "EXTERNAL_TABLE",
        "Parameters": {
            "table_type": "ICEBERG",
            "metadata_location": f"{s3_location}metadata/",
        },
    }

    try:
        glue.create_table(DatabaseName=glue_database, TableInput=table_input)
        return {
            "status": "registered",
            "table_name": table_name,
            "glue_database": glue_database,
            "column_count": len(glue_columns),
            "s3_location": s3_location,
        }
    except glue.exceptions.AlreadyExistsException:
        glue.update_table(DatabaseName=glue_database, TableInput=table_input)
        return {
            "status": "updated",
            "table_name": table_name,
            "glue_database": glue_database,
            "column_count": len(glue_columns),
        }


TOOL_DISPATCH: dict[str, Any] = {
    "convert_to_iceberg": _tool_convert_to_iceberg,
    "export_data": _tool_export_data,
    "register_glue_catalog": _tool_register_glue_catalog,
}


# ---------------------------------------------------------------------------
# Lambda handler
# ---------------------------------------------------------------------------


def handler(event: dict, context: Any) -> dict:
    """Lambda entry point — routes to Iceberg tools by name."""
    tool_name = ""
    if hasattr(context, "client_context") and context.client_context:
        custom = getattr(context.client_context, "custom", {}) or {}
        if isinstance(custom, str):
            custom = json.loads(custom)
        tool_name = custom.get("bedrockAgentCoreToolName", "")

    if "___" in tool_name:
        tool_name = tool_name.split("___")[-1]

    if not tool_name:
        tool_name = event.pop("tool_name", "")

    if tool_name not in TOOL_DISPATCH:
        available = list(TOOL_DISPATCH.keys())
        return {
            "content": [{
                "type": "text",
                "text": json.dumps(
                    {"error": f"Unknown tool: {tool_name}", "available": available}
                ),
            }]
        }

    logger.info("Invoking iceberg tool=%s", tool_name)

    try:
        result = TOOL_DISPATCH[tool_name](**event)
        return {"content": [{"type": "text", "text": json.dumps(result, default=str)}]}
    except Exception as e:
        logger.exception("Iceberg tool %s failed", tool_name)
        return {"content": [{"type": "text", "text": json.dumps({"error": str(e)})}]}
