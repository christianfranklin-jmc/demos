"""Tool: Scan and profile database metadata."""

from strands import tool

from ..drivers import get_driver


@tool
def scan_metadata(source_id: str) -> dict:
    """Scan the connected database and return a structured metadata profile.

    Returns tables, columns, data types, primary keys, foreign keys, and row counts.
    Works with any supported database type (PostgreSQL, Redshift, etc.).

    Args:
        source_id: The source identifier returned by connect_to_database.
    """
    driver = get_driver(source_id)
    return driver.scan_metadata()


@tool
def profile_database(source_id: str) -> dict:
    """Profile the connected database with column-level statistics.

    Returns per-column metrics like distinct counts, null rates, min/max values.
    Depth of profiling varies by database type.

    Args:
        source_id: The source identifier returned by connect_to_database.
    """
    driver = get_driver(source_id)
    return driver.profile_columns()
