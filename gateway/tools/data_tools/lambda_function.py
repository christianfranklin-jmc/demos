"""Gateway Lambda handler for Platform Agent data tools.

Single Lambda target that routes to 5 data tools by tool name.
Stateless — creates a fresh database driver per invocation using
env vars or event parameters for connection details.

Tool names follow MCP convention: {target}___{tool_name}
The Gateway strips the target prefix before invoking.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# ---------------------------------------------------------------------------
# Driver factory (inline to avoid importing the full platform_agent package)
# ---------------------------------------------------------------------------

_DRIVER_CLASSES: dict[str, type] = {}


def _get_driver_class(driver_type: str) -> type:
    """Lazy-load driver classes to avoid import errors for unused drivers."""
    if driver_type not in _DRIVER_CLASSES:
        if driver_type == "postgresql":
            import psycopg2  # noqa: F401
            from _postgresql_driver import PostgreSQLLambdaDriver

            _DRIVER_CLASSES["postgresql"] = PostgreSQLLambdaDriver
        elif driver_type == "redshift":
            import redshift_connector  # noqa: F401
            from _redshift_driver import RedshiftLambdaDriver

            _DRIVER_CLASSES["redshift"] = RedshiftLambdaDriver
        else:
            raise ValueError(f"Unsupported driver_type: {driver_type}")
    return _DRIVER_CLASSES[driver_type]


def _create_driver(driver_type: str, **overrides: Any) -> Any:
    """Create a database driver from env vars + optional overrides."""
    params = {
        "host": overrides.get("host", os.environ.get("DB_HOST", "")),
        "port": int(overrides.get("port", os.environ.get("DB_PORT", "5432"))),
        "database": overrides.get("database", os.environ.get("DB_NAME", "")),
        "user": overrides.get("user", os.environ.get("DB_USER", "")),
        "password": overrides.get("password", os.environ.get("DB_PASSWORD", "")),
    }
    cls = _get_driver_class(driver_type)
    driver = cls(**params)
    driver.connect()
    return driver


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------


def _tool_connect(driver_type: str, **kwargs: Any) -> dict:
    """Validate database connectivity."""
    driver = _create_driver(driver_type, **kwargs)
    result = {"status": "connected", "driver_type": driver_type}
    driver.close()
    return result


def _tool_scan_metadata(driver_type: str, **kwargs: Any) -> dict:
    """Scan database metadata: tables, columns, PKs, FKs, row counts."""
    driver = _create_driver(driver_type, **kwargs)
    result = driver.scan_metadata()
    driver.close()
    return result


def _tool_profile_database(driver_type: str, **kwargs: Any) -> dict:
    """Profile database columns: cardinality, null rates, sample values."""
    driver = _create_driver(driver_type, **kwargs)
    result = driver.profile_columns()
    driver.close()
    return result


def _tool_run_query(driver_type: str, **kwargs: Any) -> dict:
    """Execute a read-only SQL query."""
    sql = kwargs.pop("sql", "")
    max_rows = int(kwargs.pop("max_rows", 100))
    if not sql:
        raise ValueError("sql parameter is required")
    driver = _create_driver(driver_type, **kwargs)
    result = driver.execute_query(sql, max_rows=max_rows)
    driver.close()
    return result


def _tool_execute_ddl(driver_type: str, **kwargs: Any) -> dict:
    """Execute a DDL/write statement (DROP/TRUNCATE blocked)."""
    sql = kwargs.pop("sql", "")
    if not sql:
        raise ValueError("sql parameter is required")
    driver = _create_driver(driver_type, **kwargs)
    result = driver.execute_ddl(sql)
    driver.close()
    return result


TOOL_DISPATCH: dict[str, Any] = {
    "connect_to_database": _tool_connect,
    "scan_metadata": _tool_scan_metadata,
    "profile_database": _tool_profile_database,
    "run_query": _tool_run_query,
    "execute_ddl": _tool_execute_ddl,
}


# ---------------------------------------------------------------------------
# Lambda handler
# ---------------------------------------------------------------------------


def handler(event: dict, context: Any) -> dict:
    """Lambda entry point — routes to the appropriate tool by name.

    The tool name is provided by AgentCore Gateway via:
        context.client_context.custom['bedrockAgentCoreToolName']

    The event body contains the tool's input parameters as JSON.
    """
    # Extract tool name from Gateway context
    tool_name = ""
    if hasattr(context, "client_context") and context.client_context:
        custom = getattr(context.client_context, "custom", {}) or {}
        if isinstance(custom, str):
            custom = json.loads(custom)
        tool_name = custom.get("bedrockAgentCoreToolName", "")

    # Strip target prefix: "data_tools___scan_metadata" → "scan_metadata"
    if "___" in tool_name:
        tool_name = tool_name.split("___")[-1]

    # Fallback: try event body
    if not tool_name:
        tool_name = event.pop("tool_name", "")

    if tool_name not in TOOL_DISPATCH:
        available = list(TOOL_DISPATCH.keys())
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(
                        {"error": f"Unknown tool: {tool_name}. Available: {available}"}
                    ),
                }
            ]
        }

    # Extract driver_type from event or env var
    driver_type = event.pop(
        "driver_type", os.environ.get("DB_DRIVER_TYPE", "postgresql")
    )

    logger.info("Invoking tool=%s driver_type=%s", tool_name, driver_type)

    try:
        result = TOOL_DISPATCH[tool_name](driver_type=driver_type, **event)
        return {
            "content": [{"type": "text", "text": json.dumps(result, default=str)}]
        }
    except Exception as e:
        logger.exception("Tool %s failed", tool_name)
        return {
            "content": [
                {"type": "text", "text": json.dumps({"error": str(e)}, default=str)}
            ]
        }
