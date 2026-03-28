"""Tool: Execute DDL statements (guarded)."""

from strands import tool

from ..drivers import get_driver


@tool
def execute_ddl(source_id: str, sql: str) -> dict:
    """Execute a DDL statement (CREATE TABLE, INSERT) against the connected database.

    This tool is restricted: DROP and TRUNCATE are permanently blocked.
    Use this only after the user has explicitly approved the dimensional model
    design. Works with any supported database type (PostgreSQL, Redshift, etc.).

    Args:
        source_id: The source identifier returned by connect_to_database.
        sql: The DDL statement to execute (CREATE TABLE, INSERT, etc.).
    """
    driver = get_driver(source_id)
    return driver.execute_ddl(sql)
