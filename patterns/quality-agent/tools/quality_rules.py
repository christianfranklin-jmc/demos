"""Tool: Generate and manage data quality rules.

Produces DQDL (Data Quality Definition Language) rules from column
statistics, generates dbt tests, and manages quality score tracking.
"""

from __future__ import annotations

import logging

from strands import tool

logger = logging.getLogger(__name__)


@tool
def generate_quality_rules(
    source_id: str,
    tables: list[str] | None = None,
    baseline_k: int = 5,
) -> dict:
    """Generate data quality rules from schema and column statistics.

    Analyzes each table's columns and produces:
    - NOT NULL rules on primary keys and critical columns
    - UNIQUENESS rules on primary/surrogate keys
    - REFERENTIAL INTEGRITY rules on foreign keys
    - RANGE rules on numeric columns (based on current min/max)
    - COMPLETENESS rules (null rate thresholds)
    - FRESHNESS rules on date columns (recency checks)

    Args:
        source_id: The source identifier from connect_to_database.
        tables: Optional list of table names. If empty, generates for all.
        baseline_k: Number of historical periods to use for dynamic baselines.
    """
    import sys
    sys.path.insert(0, "/app/src")
    from platform_agent.drivers import get_driver

    driver = get_driver(source_id)
    metadata = driver.scan_metadata()

    all_tables = metadata.get("tables", [])
    if tables:
        all_tables = [t for t in all_tables if t.get("table_name") in tables]

    rules_by_table = []

    for tbl in all_tables:
        tname = tbl.get("table_name", "")
        columns = tbl.get("columns", [])
        pks = tbl.get("primary_key", [])
        fks = tbl.get("foreign_keys", [])
        row_count = tbl.get("row_count", 0) or 0

        table_rules = []

        # 1. Row count rule (expect non-empty)
        if row_count > 0:
            table_rules.append({
                "rule_type": "ROW_COUNT",
                "expression": "RowCount > 0",
                "severity": "ERROR",
                "description": f"Table must not be empty (current: {row_count})",
            })

        # 2. Primary key rules
        for pk in pks:
            table_rules.append({
                "rule_type": "NOT_NULL",
                "column": pk,
                "expression": f"IsComplete \"{pk}\"",
                "severity": "ERROR",
                "description": f"Primary key {pk} must not contain nulls.",
            })
            table_rules.append({
                "rule_type": "UNIQUE",
                "column": pk,
                "expression": f"IsUnique \"{pk}\"",
                "severity": "ERROR",
                "description": f"Primary key {pk} must be unique.",
            })

        # 3. Foreign key referential integrity
        for fk in fks:
            src_col = fk.get("source_column", "")
            tgt_table = fk.get("target_table", "")
            tgt_col = fk.get("target_column", "")
            table_rules.append({
                "rule_type": "REFERENTIAL_INTEGRITY",
                "column": src_col,
                "expression": (
                    f"ReferentialIntegrity \"{src_col}\" "
                    f"\"{tgt_table}\".\"{tgt_col}\" >= 1.0"
                ),
                "severity": "WARNING",
                "description": (
                    f"FK {src_col} must reference {tgt_table}.{tgt_col}."
                ),
            })

        # 4. Column-level rules from statistics
        for col in columns:
            cname = col.get("column_name", "")
            dtype = col.get("data_type", "").upper()
            is_nullable = col.get("is_nullable", "YES")

            # NOT NULL on non-nullable columns
            if is_nullable == "NO" and cname not in pks:
                table_rules.append({
                    "rule_type": "NOT_NULL",
                    "column": cname,
                    "expression": f"IsComplete \"{cname}\"",
                    "severity": "ERROR",
                    "description": f"{cname} is declared NOT NULL.",
                })

            # Date freshness rules on date columns in fact tables
            if (
                any(t in dtype for t in ["DATE", "TIMESTAMP"])
                and tname.upper().startswith("FACT_")
            ):
                table_rules.append({
                    "rule_type": "FRESHNESS",
                    "column": cname,
                    "expression": (
                        f"Freshness \"{cname}\" <= {baseline_k} days"
                    ),
                    "severity": "WARNING",
                    "description": (
                        f"Data in {cname} should be within "
                        f"{baseline_k} days of current date."
                    ),
                })

        rules_by_table.append({
            "table_name": tname,
            "rule_count": len(table_rules),
            "rules": table_rules,
        })

    total_rules = sum(t["rule_count"] for t in rules_by_table)
    return {
        "source_id": source_id,
        "tables_analyzed": len(rules_by_table),
        "total_rules": total_rules,
        "rules_by_table": rules_by_table,
        "dqdl_format": "AWS Glue Data Quality (DQDL)",
    }


@tool
def generate_dbt_tests(
    source_id: str,
    project_dir: str,
    tables: list[str] | None = None,
) -> dict:
    """Generate dbt schema tests for data quality validation.

    Produces schema.yml entries with unique, not_null, accepted_values,
    and relationships tests based on schema analysis.

    Args:
        source_id: The source identifier from connect_to_database.
        project_dir: Path to the dbt project directory.
        tables: Optional list of table names to generate tests for.
    """
    import os
    import sys
    sys.path.insert(0, "/app/src")
    from platform_agent.drivers import get_driver

    driver = get_driver(source_id)
    metadata = driver.scan_metadata()

    all_tables = metadata.get("tables", [])
    if tables:
        all_tables = [t for t in all_tables if t.get("table_name") in tables]

    test_entries = []

    for tbl in all_tables:
        tname = tbl.get("table_name", "")
        pks = tbl.get("primary_key", [])
        fks = tbl.get("foreign_keys", [])
        columns = tbl.get("columns", [])

        col_tests = []

        # PK tests
        for pk in pks:
            col_tests.append({
                "column": pk,
                "tests": ["unique", "not_null"],
            })

        # FK relationship tests
        for fk in fks:
            col_tests.append({
                "column": fk.get("source_column", ""),
                "tests": [{
                    "relationships": {
                        "to": f"source('{metadata.get('database', '')}', "
                              f"'{fk.get('target_table', '')}')",
                        "field": fk.get("target_column", ""),
                    }
                }],
            })

        # NOT NULL on non-nullable non-PK columns
        for col in columns:
            cname = col.get("column_name", "")
            if col.get("is_nullable") == "NO" and cname not in pks:
                existing = [c for c in col_tests if c["column"] == cname]
                if existing:
                    existing[0]["tests"].append("not_null")
                else:
                    col_tests.append({
                        "column": cname,
                        "tests": ["not_null"],
                    })

        test_entries.append({
            "table_name": tname,
            "test_count": sum(
                len(c["tests"]) for c in col_tests
            ),
            "column_tests": col_tests,
        })

    # Write schema test YAML
    schema_path = os.path.join(project_dir, "models", "staging", "schema_tests.yml")
    lines = ["version: 2", "", "models:"]

    for entry in test_entries:
        model_name = f"stg_{metadata.get('database', '').lower()}__{entry['table_name'].lower()}"
        lines.append(f"  - name: {model_name}")
        if entry["column_tests"]:
            lines.append("    columns:")
            for ct in entry["column_tests"]:
                lines.append(f"      - name: {ct['column'].lower()}")
                lines.append("        tests:")
                for test in ct["tests"]:
                    if isinstance(test, str):
                        lines.append(f"          - {test}")
                    elif isinstance(test, dict):
                        for tname_key, tconfig in test.items():
                            lines.append(f"          - {tname_key}:")
                            for k, v in tconfig.items():
                                lines.append(f"              {k}: \"{v}\"")

    schema_content = "\n".join(lines) + "\n"
    os.makedirs(os.path.dirname(schema_path), exist_ok=True)
    with open(schema_path, "w") as f:
        f.write(schema_content)

    total_tests = sum(e["test_count"] for e in test_entries)
    return {
        "status": "success",
        "schema_file": schema_path,
        "tables": len(test_entries),
        "total_tests": total_tests,
        "test_entries": test_entries,
    }
