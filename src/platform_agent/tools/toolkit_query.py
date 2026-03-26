"""Tool: Execute read-only SQL queries."""

from strands import tool

from ..drivers import get_driver


@tool
def run_query(source_id: str, sql: str, max_rows: int = 100) -> dict:
    """Execute a read-only SQL query against the connected database.

    Use this to inspect actual data values during discovery — distinct counts,
    sample rows, value distributions, null rates, etc. Only SELECT statements
    are allowed. Works with any supported database type (PostgreSQL, Redshift, etc.).

    Args:
        source_id: The source identifier returned by connect_to_database.
        sql: The SQL SELECT statement to execute.
        max_rows: Maximum number of rows to return. Defaults to 100.
    """
    driver = get_driver(source_id)
    return driver.execute_query(sql, max_rows=max_rows)
