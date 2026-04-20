"""Tool: Scan and profile database metadata."""

from uuid import uuid4

from strands import tool

from ..drivers import get_driver


def _emit_progress(tool_name: str, note: str, index: int | None = None, total: int | None = None) -> None:
    """Emit a tool_progress SSE event if a heartbeat emitter is bound.

    No-op in CLI / Streamlit paths (ContextVar unset). See ADR-015 D9.
    """
    try:
        from ..api.events import ToolProgressEvent
        from ..api.sse import heartbeat_emitter
    except ImportError:
        return
    emitter = heartbeat_emitter.get()
    if emitter is None:
        return
    emitter(
        ToolProgressEvent(
            run_id=uuid4(),  # overridden by make_progress_emitter
            tool=tool_name,
            note=note,
            index=index,
            total=total,
        )
    )


@tool
def scan_metadata(source_id: str) -> dict:
    """Scan the connected database and return a structured metadata profile.

    Returns tables, columns, data types, primary keys, foreign keys, and row counts.
    Works with any supported database type (PostgreSQL, Redshift, etc.).

    Args:
        source_id: The source identifier returned by connect_to_database.
    """
    _emit_progress("scan_metadata", "opening connection")
    driver = get_driver(source_id)
    _emit_progress("scan_metadata", "reading information_schema")
    result = driver.scan_metadata()
    tables = result.get("tables") if isinstance(result, dict) else None
    if isinstance(tables, list):
        _emit_progress("scan_metadata", f"discovered {len(tables)} tables", total=len(tables))
    return result


@tool
def profile_database(source_id: str) -> dict:
    """Profile the connected database with column-level statistics.

    Returns per-column metrics like distinct counts, null rates, min/max values.
    Depth of profiling varies by database type.

    Args:
        source_id: The source identifier returned by connect_to_database.
    """
    _emit_progress("profile_database", "opening connection")
    driver = get_driver(source_id)
    _emit_progress("profile_database", "computing column statistics")
    return driver.profile_columns()
