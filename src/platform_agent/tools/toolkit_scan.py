"""Tool: Scan and profile database metadata."""

from strands import tool

from . import _toolkit_client


@tool
def scan_metadata(source_id: str) -> dict:
    """Scan the connected database and return a structured metadata profile.

    Uses phData Toolkit CLI if available for richer metadata including ERD graph
    and constraint details. Falls back to information_schema queries otherwise.

    Returns tables, columns, data types, primary keys, foreign keys, and row counts.

    Args:
        source_id: The source identifier returned by connect_to_database.
    """
    return _toolkit_client.scan(source_id)


@tool
def profile_database(source_id: str) -> dict:
    """Profile the connected database with column-level statistics.

    Runs phData Toolkit's profiler to compute per-column metrics: distinct_count,
    min, max, null_count, negative_count, zero_count. This is more detailed than
    scan_metadata and useful for data quality assessment and discovery.

    Requires phData Toolkit CLI to be available.

    Args:
        source_id: The source identifier returned by connect_to_database.
    """
    return _toolkit_client.profile(source_id)
