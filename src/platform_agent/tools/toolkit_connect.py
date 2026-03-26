"""Tool: Connect to an AWS data service (PostgreSQL, Redshift, etc.)."""

from strands import tool

from ..drivers import DRIVER_REGISTRY, create_driver


@tool
def connect_to_database(
    host: str,
    port: int,
    database: str,
    user: str,
    password: str,
    driver_type: str = "postgresql",
    source_id: str = "",
) -> dict:
    """Connect to a database on AWS (PostgreSQL, Redshift, or other supported types).

    Establishes a connection and registers it for subsequent scan, query, and DDL operations.
    Returns a source_id that must be used in all follow-up tool calls.

    Args:
        host: The database hostname (e.g., my-instance.abc123.us-east-1.rds.amazonaws.com).
        port: The database port (5432 for PostgreSQL, 5439 for Redshift).
        database: The database name to connect to.
        user: The database username.
        password: The database password.
        driver_type: Database type — "postgresql" or "redshift". Defaults to "postgresql".
        source_id: Optional identifier for this connection. Auto-generated if not provided.
    """
    source_id = source_id or f"{driver_type}_{database}"

    driver = create_driver(
        driver_type=driver_type,
        source_id=source_id,
        host=host,
        port=port,
        database=database,
        user=user,
        password=password,
    )
    return {
        "status": "connected",
        "source_id": source_id,
        "driver_type": driver.driver_type,
        "database": database,
        "available_drivers": list(DRIVER_REGISTRY.keys()),
    }
