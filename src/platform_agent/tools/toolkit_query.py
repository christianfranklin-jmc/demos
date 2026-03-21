"""Tool: Execute read-only SQL queries."""

from strands import tool

from . import _toolkit_client


@tool
def run_query(source_id: str, sql: str, max_rows: int = 100) -> dict:
    """Execute a read-only SQL query against the connected database.

    Use this to inspect actual data values during discovery — distinct counts,
    sample rows, value distributions, null rates, etc. Only SELECT statements
    are allowed.

    Args:
        source_id: The source identifier returned by connect_to_database.
        sql: The SQL SELECT statement to execute.
        max_rows: Maximum number of rows to return. Defaults to 100.
    """
    return _toolkit_client.query(source_id, sql, max_rows=max_rows)
