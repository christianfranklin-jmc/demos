"""Tool: Validate migration by comparing source and target row counts.

Connects to both Snowflake (source) and the AWS target (Athena/Redshift/RDS)
to verify data completeness after migration.
"""

from __future__ import annotations

import logging

from strands import tool

logger = logging.getLogger(__name__)


@tool
def validate_row_counts(
    source_id: str,
    tables: list[str] | None = None,
) -> dict:
    """Validate migration by comparing row counts on the source database.

    Queries the source (Snowflake) to get exact row counts for all tables
    or a specific subset. Returns a validation report that can be compared
    against target counts.

    Args:
        source_id: The source identifier from connect_to_database.
        tables: Optional list of table names to validate. If empty, validates all.
    """
    import sys
    sys.path.insert(0, "/app/src")
    from platform_agent.drivers import get_driver

    driver = get_driver(source_id)
    metadata = driver.scan_metadata()

    results = []
    all_tables = metadata.get("tables", [])

    for table in all_tables:
        tname = table.get("table_name", "")

        # Skip if specific tables requested and this isn't one
        if tables and tname not in tables:
            continue

        # Get exact count from source (metadata may be approximate)
        try:
            count_result = driver.execute_query(
                f'SELECT COUNT(*) AS cnt FROM "{tname}"', max_rows=1
            )
            exact_count = count_result["rows"][0]["cnt"] if count_result["rows"] else 0
        except Exception as e:
            exact_count = table.get("row_count", 0)
            logger.warning("Could not get exact count for %s: %s", tname, e)

        results.append({
            "table_name": tname,
            "source_count": exact_count,
            "metadata_count": table.get("row_count", 0),
            "column_count": len(table.get("columns", [])),
        })

    total_rows = sum(r["source_count"] for r in results)

    return {
        "source_id": source_id,
        "database": metadata.get("database", ""),
        "schema": metadata.get("schema", ""),
        "tables_validated": len(results),
        "total_source_rows": total_rows,
        "results": results,
        "status": "source_counts_captured",
        "next_step": (
            "After migration, run the same validation against the target "
            "and compare counts to verify data completeness."
        ),
    }


@tool
def generate_validation_report(
    source_counts: dict,
    target_counts: dict | None = None,
) -> dict:
    """Generate a migration validation report comparing source and target.

    Produces a pass/fail report for each table with delta analysis.

    Args:
        source_counts: Output from validate_row_counts on the source.
        target_counts: Output from validate_row_counts on the target (optional).
    """
    if not target_counts:
        return {
            "status": "incomplete",
            "message": (
                "Target counts not provided. Run validate_row_counts "
                "on the target database after migration."
            ),
            "source_summary": {
                "tables": source_counts.get("tables_validated", 0),
                "total_rows": source_counts.get("total_source_rows", 0),
            },
        }

    source_by_table = {
        r["table_name"]: r["source_count"]
        for r in source_counts.get("results", [])
    }
    target_by_table = {
        r["table_name"]: r["source_count"]
        for r in target_counts.get("results", [])
    }

    report = []
    all_pass = True

    for tname, src_count in source_by_table.items():
        tgt_count = target_by_table.get(tname)
        if tgt_count is None:
            report.append({
                "table_name": tname,
                "status": "MISSING",
                "source_count": src_count,
                "target_count": None,
                "delta": src_count,
            })
            all_pass = False
        elif src_count == tgt_count:
            report.append({
                "table_name": tname,
                "status": "PASS",
                "source_count": src_count,
                "target_count": tgt_count,
                "delta": 0,
            })
        else:
            delta = abs(src_count - tgt_count)
            delta_pct = round(delta / max(src_count, 1) * 100, 4)
            report.append({
                "table_name": tname,
                "status": "FAIL" if delta_pct > 0.01 else "WARN",
                "source_count": src_count,
                "target_count": tgt_count,
                "delta": delta,
                "delta_pct": delta_pct,
            })
            if delta_pct > 0.01:
                all_pass = False

    return {
        "status": "PASS" if all_pass else "FAIL",
        "tables_checked": len(report),
        "tables_passed": sum(1 for r in report if r["status"] == "PASS"),
        "tables_failed": sum(
            1 for r in report if r["status"] in ("FAIL", "MISSING")
        ),
        "total_source_rows": sum(source_by_table.values()),
        "total_target_rows": sum(
            v for v in target_by_table.values() if v is not None
        ),
        "results": report,
    }
