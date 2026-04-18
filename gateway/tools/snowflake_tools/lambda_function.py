"""Gateway Lambda handler for Snowflake-specific tools.

Provides tools for semantic metadata extraction and cross-database
row count validation. Uses snowflake-connector-python directly
(self-contained — Lambda can't import from src/platform_agent/).

Tool names follow MCP convention: {target}___{tool_name}
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def _serialize(v: Any) -> Any:
    """Convert non-JSON-serializable types to strings."""
    if v is None:
        return None
    if isinstance(v, (int, float, str, bool)):
        return v
    return str(v)


def _get_snowflake_conn() -> Any:
    """Create a Snowflake connection from env vars."""
    import snowflake.connector

    return snowflake.connector.connect(
        account=os.environ.get("SF_ACCOUNT", ""),
        user=os.environ.get("SF_USER", ""),
        password=os.environ.get("SF_PASSWORD", ""),
        warehouse=os.environ.get("SF_WAREHOUSE", ""),
        database=os.environ.get("SF_DATABASE", ""),
        schema=os.environ.get("SF_SCHEMA", "PUBLIC"),
        role=os.environ.get("SF_ROLE", ""),
    )


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------


def _tool_extract_semantic_metadata(**kwargs: Any) -> dict:
    """Extract semantic metadata from Snowflake: column comments, tags, descriptions."""
    import snowflake.connector as sf_conn

    conn = _get_snowflake_conn()
    cur = conn.cursor(sf_conn.DictCursor)
    database = os.environ.get("SF_DATABASE", "")
    schema = os.environ.get("SF_SCHEMA", "PUBLIC")

    # Table comments
    cur.execute(f"""
        SELECT TABLE_NAME, COMMENT
        FROM {database}.INFORMATION_SCHEMA.TABLES
        WHERE TABLE_SCHEMA = '{schema}' AND TABLE_TYPE = 'BASE TABLE'
        ORDER BY TABLE_NAME
    """)
    table_comments = {row["TABLE_NAME"]: row["COMMENT"] for row in cur.fetchall()}

    # Column comments
    cur.execute(f"""
        SELECT TABLE_NAME, COLUMN_NAME, COMMENT, DATA_TYPE
        FROM {database}.INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = '{schema}'
        ORDER BY TABLE_NAME, ORDINAL_POSITION
    """)
    column_data = cur.fetchall()

    # Tags (if accessible)
    tags_by_object: dict[str, list[dict]] = {}
    try:
        cur.execute(f"""
            SELECT * FROM TABLE(
                {database}.INFORMATION_SCHEMA.TAG_REFERENCES_ALL_COLUMNS(
                    '{database}.{schema}', 'TABLE'
                )
            )
        """)
        for row in cur.fetchall():
            obj = row.get("OBJECT_NAME", "")
            tags_by_object.setdefault(obj, []).append({
                "tag_name": row.get("TAG_NAME", ""),
                "tag_value": row.get("TAG_VALUE", ""),
                "column_name": row.get("COLUMN_NAME"),
            })
    except Exception:
        logger.info("Tag references not accessible — skipping")

    cur.close()
    conn.close()

    # Build result
    tables: dict[str, dict] = {}
    for row in column_data:
        tname = row["TABLE_NAME"]
        if tname not in tables:
            tables[tname] = {
                "table_name": tname,
                "table_comment": table_comments.get(tname, ""),
                "tags": tags_by_object.get(tname, []),
                "columns": [],
            }
        tables[tname]["columns"].append({
            "column_name": row["COLUMN_NAME"],
            "data_type": row["DATA_TYPE"],
            "comment": row.get("COMMENT", ""),
        })

    return {
        "source": "snowflake",
        "database": database,
        "schema": schema,
        "tables": list(tables.values()),
    }


def _tool_validate_row_counts(**kwargs: Any) -> dict:
    """Compare row counts between Snowflake source and AWS target."""
    source_table = kwargs.get("source_table", "")
    target_table = kwargs.get("target_table", "")
    target_engine = kwargs.get("target_engine", "athena")

    if not source_table:
        raise ValueError("source_table is required")

    # Get Snowflake count
    conn = _get_snowflake_conn()
    cur = conn.cursor()
    database = os.environ.get("SF_DATABASE", "")
    schema = os.environ.get("SF_SCHEMA", "PUBLIC")
    cur.execute(f"SELECT COUNT(*) FROM {database}.{schema}.{source_table}")
    source_count = cur.fetchone()[0]
    cur.close()
    conn.close()

    # Get target count (via Athena or Redshift — placeholder)
    target_count = None
    if target_table and target_engine == "athena":
        try:
            # Placeholder — actual Athena query needs
            # query execution, result polling, and S3 output parsing
            target_count = -1  # Not yet implemented
        except Exception:
            target_count = -1

    result = {
        "source_table": source_table,
        "source_count": source_count,
        "target_table": target_table or source_table,
        "target_count": target_count,
        "match": source_count == target_count if target_count is not None else None,
    }

    if target_count is not None and source_count != target_count:
        result["delta"] = abs(source_count - (target_count or 0))
        result["delta_pct"] = (
            round(result["delta"] / max(source_count, 1) * 100, 4)
        )

    return result


TOOL_DISPATCH: dict[str, Any] = {
    "extract_semantic_metadata": _tool_extract_semantic_metadata,
    "validate_row_counts": _tool_validate_row_counts,
}


# ---------------------------------------------------------------------------
# Lambda handler
# ---------------------------------------------------------------------------


def handler(event: dict, context: Any) -> dict:
    """Lambda entry point — routes to Snowflake tools by name."""
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

    logger.info("Invoking snowflake tool=%s", tool_name)

    try:
        result = TOOL_DISPATCH[tool_name](**event)
        return {"content": [{"type": "text", "text": json.dumps(result, default=str)}]}
    except Exception as e:
        logger.exception("Snowflake tool %s failed", tool_name)
        return {"content": [{"type": "text", "text": json.dumps({"error": str(e)})}]}
