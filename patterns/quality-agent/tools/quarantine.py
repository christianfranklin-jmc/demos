"""Tool: Quarantine management for data quality failures.

Provides tools to identify failing records, isolate them into quarantine
tables/S3 prefixes, and generate remediation scripts.
"""

from __future__ import annotations

import logging

from strands import tool

logger = logging.getLogger(__name__)


@tool
def identify_quality_failures(
    source_id: str,
    table_name: str,
    checks: list[dict] | None = None,
) -> dict:
    """Run targeted quality checks and identify failing records.

    Executes SQL-based quality checks (null checks, range violations,
    duplicate detection, orphan key detection) and returns failing
    record counts and samples.

    Args:
        source_id: The source identifier from connect_to_database.
        table_name: Table to check.
        checks: List of check definitions. Each has:
            - type: "null_check", "duplicate", "range", "orphan_key"
            - column: Column to check
            - params: Additional parameters (min, max, ref_table, ref_column)
            If empty, auto-generates checks from schema.
    """
    import sys
    sys.path.insert(0, "/app/src")
    from platform_agent.drivers import get_driver

    driver = get_driver(source_id)

    # Auto-generate checks if not provided
    if not checks:
        metadata = driver.scan_metadata()
        tbl = next(
            (t for t in metadata.get("tables", [])
             if t.get("table_name") == table_name),
            None,
        )
        if not tbl:
            return {"error": f"Table {table_name} not found in metadata."}
        checks = _auto_generate_checks(tbl)

    results = []
    total_failures = 0

    for check in checks:
        check_type = check.get("type", "")
        column = check.get("column", "")
        params = check.get("params", {})

        try:
            if check_type == "null_check":
                sql = (
                    f'SELECT COUNT(*) AS cnt FROM "{table_name}" '
                    f'WHERE "{column}" IS NULL'
                )
                result = driver.execute_query(sql, max_rows=1)
                fail_count = _extract_count(result)

            elif check_type == "duplicate":
                sql = (
                    f'SELECT "{column}", COUNT(*) AS dup_count '
                    f'FROM "{table_name}" '
                    f'GROUP BY "{column}" HAVING COUNT(*) > 1 '
                    f'ORDER BY dup_count DESC'
                )
                result = driver.execute_query(sql, max_rows=10)
                fail_count = result.get("row_count", 0)

            elif check_type == "range":
                min_val = params.get("min", "")
                max_val = params.get("max", "")
                conditions = []
                if min_val != "":
                    conditions.append(f'"{column}" < {min_val}')
                if max_val != "":
                    conditions.append(f'"{column}" > {max_val}')
                if conditions:
                    where = " OR ".join(conditions)
                    sql = (
                        f'SELECT COUNT(*) AS cnt FROM "{table_name}" '
                        f'WHERE {where}'
                    )
                    result = driver.execute_query(sql, max_rows=1)
                    fail_count = _extract_count(result)
                else:
                    fail_count = 0

            elif check_type == "orphan_key":
                ref_table = params.get("ref_table", "")
                ref_column = params.get("ref_column", "")
                sql = (
                    f'SELECT COUNT(*) AS cnt FROM "{table_name}" t '
                    f'LEFT JOIN "{ref_table}" r '
                    f'ON t."{column}" = r."{ref_column}" '
                    f'WHERE r."{ref_column}" IS NULL '
                    f'AND t."{column}" IS NOT NULL'
                )
                result = driver.execute_query(sql, max_rows=1)
                fail_count = _extract_count(result)

            else:
                fail_count = 0

            total_failures += fail_count
            results.append({
                "check_type": check_type,
                "column": column,
                "failures": fail_count,
                "status": "PASS" if fail_count == 0 else "FAIL",
            })

        except Exception as e:
            results.append({
                "check_type": check_type,
                "column": column,
                "failures": -1,
                "status": "ERROR",
                "error": str(e)[:100],
            })

    return {
        "table_name": table_name,
        "checks_run": len(results),
        "total_failures": total_failures,
        "overall_status": "PASS" if total_failures == 0 else "FAIL",
        "results": results,
    }


@tool
def generate_remediation_plan(
    table_name: str,
    quality_results: dict,
) -> dict:
    """Generate a remediation plan for quality failures.

    Produces actionable SQL statements to fix or quarantine failing
    records based on quality check results.

    Args:
        table_name: The table with quality failures.
        quality_results: Output from identify_quality_failures.
    """
    remediation_steps = []

    for check in quality_results.get("results", []):
        if check.get("status") != "FAIL":
            continue

        check_type = check.get("check_type", "")
        column = check.get("column", "")
        failures = check.get("failures", 0)

        if check_type == "null_check":
            remediation_steps.append({
                "issue": f"{failures} NULL values in {column}",
                "severity": "HIGH" if column.endswith("_KEY") else "MEDIUM",
                "options": [
                    {
                        "action": "quarantine",
                        "sql": (
                            f'INSERT INTO quarantine."{table_name}" '
                            f'SELECT *, \'{check_type}\' AS failure_reason, '
                            f'CURRENT_TIMESTAMP AS quarantined_at '
                            f'FROM "{table_name}" WHERE "{column}" IS NULL'
                        ),
                    },
                    {
                        "action": "default_value",
                        "sql": (
                            f'UPDATE "{table_name}" '
                            f'SET "{column}" = \'UNKNOWN\' '
                            f'WHERE "{column}" IS NULL'
                        ),
                    },
                ],
            })
        elif check_type == "duplicate":
            remediation_steps.append({
                "issue": f"Duplicate values in {column}",
                "severity": "HIGH",
                "options": [
                    {
                        "action": "deduplicate",
                        "sql": (
                            f"-- Keep the latest row per {column}\n"
                            f'DELETE FROM "{table_name}" '
                            f"WHERE ROWID NOT IN ("
                            f'SELECT MAX(ROWID) FROM "{table_name}" '
                            f'GROUP BY "{column}")'
                        ),
                    },
                ],
            })
        elif check_type == "orphan_key":
            remediation_steps.append({
                "issue": f"Orphaned foreign keys in {column}",
                "severity": "MEDIUM",
                "options": [
                    {
                        "action": "quarantine",
                        "sql": (
                            f"-- Move orphaned records to quarantine\n"
                            f'INSERT INTO quarantine."{table_name}" '
                            f'SELECT t.*, \'{check_type}\' AS failure_reason '
                            f'FROM "{table_name}" t '
                            f"WHERE NOT EXISTS (SELECT 1 FROM ... "
                            f"WHERE ...)"
                        ),
                    },
                ],
            })

    return {
        "table_name": table_name,
        "total_issues": len(remediation_steps),
        "high_severity": sum(
            1 for s in remediation_steps if s["severity"] == "HIGH"
        ),
        "remediation_steps": remediation_steps,
        "recommendation": (
            "Review and approve each remediation SQL before execution. "
            "Always quarantine before deleting."
        ),
    }


def _auto_generate_checks(table: dict) -> list[dict]:
    """Auto-generate quality checks from schema metadata."""
    checks = []
    pks = table.get("primary_key", [])
    fks = table.get("foreign_keys", [])

    # PK null + duplicate checks
    for pk in pks:
        checks.append({"type": "null_check", "column": pk})
        checks.append({"type": "duplicate", "column": pk})

    # FK orphan checks
    for fk in fks:
        checks.append({
            "type": "orphan_key",
            "column": fk.get("source_column", ""),
            "params": {
                "ref_table": fk.get("target_table", ""),
                "ref_column": fk.get("target_column", ""),
            },
        })

    # Non-nullable column null checks
    for col in table.get("columns", []):
        cname = col.get("column_name", "")
        if col.get("is_nullable") == "NO" and cname not in pks:
            checks.append({"type": "null_check", "column": cname})

    return checks


def _extract_count(result: dict) -> int:
    """Extract count from a single-row query result."""
    rows = result.get("rows", [])
    if not rows:
        return 0
    row = rows[0]
    # Handle both lowercase and uppercase column names
    return row.get("cnt", row.get("CNT", 0))
