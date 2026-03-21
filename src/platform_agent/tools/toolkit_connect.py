"""Tool: Connect to an AWS data service."""

from strands import tool

from . import _toolkit_client


@tool
def connect_to_database(
    host: str,
    port: int,
    database: str,
    user: str,
    password: str,
    source_id: str = "",
) -> dict:
    """Connect to a PostgreSQL database on AWS.

    Establishes a connection and registers it for subsequent scan, query, and DDL operations.
    Returns a source_id that must be used in all follow-up tool calls.

    The source_id should match the datasource name in toolkit.conf if using phData Toolkit
    (e.g., "northwinds"). If not provided, one is generated automatically.

    Args:
        host: The database hostname (e.g., my-instance.abc123.us-east-1.rds.amazonaws.com).
        port: The database port (typically 5432 for PostgreSQL).
        database: The database name to connect to.
        user: The database username.
        password: The database password.
        source_id: Optional identifier for this connection. Should match toolkit.conf datasource name.
    """
    session = _toolkit_client.connect(
        host=host,
        port=port,
        database=database,
        user=user,
        password=password,
        source_id=source_id or None,
    )
    return {
        "status": "connected",
        "source_id": session.source_id,
        "service": session.service,
        "database": session.database,
        "toolkit_available": _toolkit_client._toolkit_available(),
    }
