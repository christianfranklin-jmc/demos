"""DatabaseDriver protocol — the interface all database backends implement.

Tools program against this protocol. Each driver owns its own:
- Connection logic (psycopg2, redshift_connector, snowflake-connector, etc.)
- Metadata queries (information_schema variants, system views)
- dbt adapter config (profiles.yml type + connection params)
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class DatabaseDriver(Protocol):
    """Interface that every database backend must implement."""

    driver_type: str  # "postgresql", "redshift", "snowflake", "databricks"

    def connect(self, **kwargs: Any) -> None:
        """Establish the database connection."""
        ...

    def close(self) -> None:
        """Close the database connection."""
        ...

    def execute_query(self, sql: str, max_rows: int = 100) -> dict:
        """Execute a read-only SQL query and return structured results.

        Returns:
            {"columns": [...], "rows": [...], "row_count": int, "truncated": bool}
        """
        ...

    def execute_ddl(self, sql: str) -> dict:
        """Execute a DDL/write statement (DROP/TRUNCATE blocked).

        Returns:
            {"status": "success", "statement": str}
        """
        ...

    def scan_metadata(self) -> dict:
        """Scan database metadata: tables, columns, PKs, FKs, row counts.

        Returns:
            {"source_id": str, "database": str, "schema": str, "tables": [...]}
        """
        ...

    def profile_columns(self) -> dict:
        """Profile columns: cardinality, null rates, min/max, sample values.

        Returns:
            Same structure as scan_metadata with additional per-column stats.
        """
        ...

    def get_dbt_adapter(self) -> str:
        """Return the dbt adapter name: 'postgres', 'redshift', 'snowflake', 'databricks'."""
        ...

    def get_dbt_profile_config(self) -> dict:
        """Return connection config for dbt profiles.yml."""
        ...
