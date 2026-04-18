"""Tool: Generate Iceberg CREATE TABLE DDL from Snowflake schema.

Maps Snowflake data types to Iceberg/Glue-compatible types and
generates partition specifications from clustering keys or
recommended date columns.
"""

from __future__ import annotations

import logging

from strands import tool

logger = logging.getLogger(__name__)

# Snowflake → Iceberg type mapping
SF_TO_ICEBERG: dict[str, str] = {
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


def _map_type(
    sf_type: str,
    precision: int | None = None,
    scale: int | None = None,
) -> str:
    """Map Snowflake type to Iceberg type."""
    base = sf_type.upper().split("(")[0].strip()
    iceberg = SF_TO_ICEBERG.get(base, "string")
    if iceberg == "decimal" and precision is not None:
        return f"decimal({precision}, {scale or 0})"
    return iceberg


@tool
def generate_iceberg_ddl(
    table_name: str,
    columns: list[dict],
    s3_bucket: str,
    glue_database: str = "semantic_lake",
    partition_key: str = "",
    partition_transform: str = "month",
    table_comment: str = "",
) -> dict:
    """Generate Iceberg CREATE TABLE DDL for a Snowflake table.

    Produces a complete CREATE EXTERNAL TABLE statement compatible with
    AWS Glue Catalog and Athena, with Iceberg table format.

    Args:
        table_name: Target table name (lowercase).
        columns: List of column dicts with column_name, data_type,
                 numeric_precision, numeric_scale, is_nullable, comment.
        s3_bucket: S3 bucket for Iceberg data files.
        glue_database: Glue Catalog database name.
        partition_key: Column to partition by (empty for no partitioning).
        partition_transform: Partition transform (day, month, year, bucket).
        table_comment: Optional table comment.
    """
    target_name = table_name.lower()
    s3_location = f"s3://{s3_bucket}/iceberg/{glue_database}/{target_name}/"

    # Build column definitions
    col_defs = []
    for col in columns:
        col_name = col.get("column_name", "").lower()
        sf_type = col.get("data_type", "VARCHAR")
        precision = col.get("numeric_precision")
        scale = col.get("numeric_scale")
        iceberg_type = _map_type(sf_type, precision, scale)
        nullable = "" if col.get("is_nullable", "YES") == "YES" else " NOT NULL"
        comment = col.get("comment", "")
        comment_sql = f" COMMENT '{comment}'" if comment else ""
        col_defs.append(f"  {col_name} {iceberg_type}{nullable}{comment_sql}")

    columns_sql = ",\n".join(col_defs)

    # Partition spec
    partition_clause = ""
    if partition_key:
        pk = partition_key.lower()
        partition_clause = f"\nPARTITIONED BY ({partition_transform}({pk}))"

    # Comment
    comment_clause = ""
    if table_comment:
        escaped = table_comment.replace("'", "''")
        comment_clause = f"\nCOMMENT '{escaped}'"

    ddl = f"""CREATE TABLE IF NOT EXISTS {glue_database}.{target_name} (
{columns_sql}
)
USING iceberg{partition_clause}{comment_clause}
LOCATION '{s3_location}'
TBLPROPERTIES (
  'table_type' = 'ICEBERG',
  'format-version' = '2',
  'write.format.default' = 'parquet',
  'write.parquet.compression-codec' = 'zstd'
);"""

    # Build column mapping for reference
    col_mapping = []
    for col in columns:
        sf_type = col.get("data_type", "VARCHAR")
        precision = col.get("numeric_precision")
        scale = col.get("numeric_scale")
        col_mapping.append({
            "column": col.get("column_name", "").lower(),
            "snowflake_type": sf_type,
            "iceberg_type": _map_type(sf_type, precision, scale),
        })

    return {
        "table_name": target_name,
        "glue_database": glue_database,
        "ddl": ddl,
        "s3_location": s3_location,
        "column_count": len(col_defs),
        "partition_key": partition_key,
        "partition_transform": partition_transform,
        "column_mapping": col_mapping,
    }
