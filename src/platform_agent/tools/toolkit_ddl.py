"""Tool: Execute DDL statements (guarded)."""

from strands import tool

from . import _toolkit_client


@tool
def execute_ddl(source_id: str, sql: str) -> dict:
    """Execute a DDL statement (CREATE TABLE, INSERT) against the connected database.

    This tool is restricted: DROP and TRUNCATE are permanently blocked.
    Use this only after the user has explicitly approved the dimensional model
    design. All writes should target the designated output schema.

    Args:
        source_id: The source identifier returned by connect_to_database.
        sql: The DDL statement to execute (CREATE TABLE, INSERT, etc.).
    """
    return _toolkit_client.execute_ddl(source_id, sql)
