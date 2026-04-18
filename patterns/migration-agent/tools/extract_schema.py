"""Tool: Extract and analyze Snowflake schema for migration planning.

Provides enriched schema extraction beyond basic scan_metadata —
includes clustering keys, table/column comments, tags, and
migration strategy recommendations.
"""

from __future__ import annotations

import logging
from typing import Any

from strands import tool

logger = logging.getLogger(__name__)


@tool
def extract_snowflake_schema(
    source_id: str,
    include_comments: bool = True,
    include_clustering: bool = True,
    include_row_counts: bool = True,
) -> dict:
    """Extract a comprehensive Snowflake schema profile for migration planning.

    Goes beyond scan_metadata by analyzing table structure to recommend
    migration strategies (full load vs incremental), partitioning schemes,
    and Iceberg type mappings.

    Args:
        source_id: The source identifier from connect_to_database.
        include_comments: Include table/column comments from Snowflake.
        include_clustering: Include clustering key information.
        include_row_counts: Include row counts for sizing estimates.
    """
    # Import here to avoid circular deps at module load
    import sys
    sys.path.insert(0, "/app/src")
    from platform_agent.drivers import get_driver

    driver = get_driver(source_id)
    metadata = driver.scan_metadata()

    # Enrich with migration recommendations
    tables_analysis = []
    for table in metadata.get("tables", []):
        row_count = table.get("row_count", 0) or 0
        columns = table.get("columns", [])

        # Detect date columns for partitioning
        date_cols = [
            c["column_name"] for c in columns
            if c.get("data_type", "").upper() in (
                "DATE", "TIMESTAMP", "TIMESTAMP_NTZ", "TIMESTAMP_TZ",
                "TIMESTAMP_LTZ", "DATETIME",
            )
        ]

        # Classify migration strategy
        table_name = table.get("table_name", "")
        if table_name.upper().startswith("DIM_"):
            strategy = "full_load"
            strategy_reason = "Dimension table — full load is appropriate"
        elif table_name.upper().startswith("FACT_") and date_cols:
            if row_count > 1_000_000:
                strategy = "incremental"
                strategy_reason = (
                    f"Large fact table ({row_count:,} rows) "
                    f"with date column(s): {', '.join(date_cols)}"
                )
            else:
                strategy = "full_load"
                strategy_reason = (
                    f"Small fact table ({row_count:,} rows) — "
                    f"full load is simpler"
                )
        elif row_count > 5_000_000:
            strategy = "incremental"
            strategy_reason = (
                f"Large table ({row_count:,} rows) — "
                f"incremental recommended"
            )
        else:
            strategy = "full_load"
            strategy_reason = f"Standard table ({row_count:,} rows)"

        # Recommend partition key
        partition_key = None
        if date_cols and (
            table_name.upper().startswith("FACT_") or row_count > 100_000
        ):
            partition_key = date_cols[0]

        analysis: dict[str, Any] = {
            "table_name": table_name,
            "row_count": row_count,
            "column_count": len(columns),
            "primary_key": table.get("primary_key", []),
            "foreign_keys": table.get("foreign_keys", []),
            "date_columns": date_cols,
            "migration_strategy": strategy,
            "strategy_reason": strategy_reason,
            "recommended_partition_key": partition_key,
        }

        if include_comments and table.get("comment"):
            analysis["comment"] = table["comment"]

        if include_clustering and table.get("clustering_key"):
            analysis["clustering_key"] = table["clustering_key"]

        # Type mapping summary
        type_counts: dict[str, int] = {}
        for col in columns:
            dt = col.get("data_type", "UNKNOWN").upper()
            base = dt.split("(")[0]
            type_counts[base] = type_counts.get(base, 0) + 1
        analysis["type_distribution"] = type_counts

        tables_analysis.append(analysis)

    return {
        "source_id": source_id,
        "database": metadata.get("database", ""),
        "schema": metadata.get("schema", ""),
        "table_count": len(tables_analysis),
        "total_rows": sum(t["row_count"] for t in tables_analysis),
        "tables": tables_analysis,
        "migration_summary": {
            "full_load": sum(
                1 for t in tables_analysis
                if t["migration_strategy"] == "full_load"
            ),
            "incremental": sum(
                1 for t in tables_analysis
                if t["migration_strategy"] == "incremental"
            ),
        },
    }
