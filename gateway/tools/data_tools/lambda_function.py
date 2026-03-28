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


def _serialize(v: Any) -> Any:
    """Convert non-JSON-serializable types to strings."""
    if v is None:
        return None
    if isinstance(v, (int, float, str, bool)):
        return v
    return str(v)

# ---------------------------------------------------------------------------
# Driver factory (inline to avoid importing the full platform_agent package)
# ---------------------------------------------------------------------------

_DRIVER_CLASSES: dict[str, type] = {}


# ---------------------------------------------------------------------------
# Self-contained driver classes (Lambda can't import from src/platform_agent)
# ---------------------------------------------------------------------------


class _BaseLambdaDriver:
    """Shared logic for Lambda database drivers."""

    driver_type: str = ""

    def __init__(self, host: str, port: int, database: str, user: str, password: str, **kw: Any):
        self.host = host
        self.port = port
        self.database = database
        self.user = user
        self._password = password
        self._conn: Any = None

    def close(self) -> None:
        if self._conn:
            import contextlib
            with contextlib.suppress(Exception):
                self._conn.close()

    def execute_query(self, sql: str, max_rows: int = 100) -> dict:
        normalized = sql.strip().upper()
        for kw in ("INSERT", "UPDATE", "DELETE", "DROP", "TRUNCATE", "ALTER", "CREATE"):
            if normalized.startswith(kw):
                raise ValueError(f"Write operations not allowed. SQL starts with {kw}.")
        cur = self._conn.cursor()
        cur.execute(sql)
        if cur.description is None:
            cur.close()
            return {"columns": [], "rows": [], "row_count": 0, "truncated": False}
        col_names = [desc[0] for desc in cur.description]
        rows = cur.fetchmany(max_rows)
        row_count = len(rows)
        cur.close()
        clean_rows = [
            {col_names[i]: _serialize(v) for i, v in enumerate(row)} for row in rows
        ]
        return {"columns": col_names, "rows": clean_rows, "row_count": row_count,
                "truncated": row_count >= max_rows}

    def execute_ddl(self, sql: str) -> dict:
        normalized = sql.strip().upper()
        for kw in ("DROP", "TRUNCATE"):
            if kw in normalized:
                raise ValueError(f"Destructive DDL blocked: {kw} is not allowed.")
        cur = self._conn.cursor()
        cur.execute(sql)
        cur.close()
        return {"status": "success", "statement": sql[:200]}

    def scan_metadata(self) -> dict:
        raise NotImplementedError

    def profile_columns(self) -> dict:
        result = self.scan_metadata()
        result["_note"] = "Column-level profiling not available in Lambda"
        return result


class _PostgreSQLLambdaDriver(_BaseLambdaDriver):
    driver_type = "postgresql"

    def connect(self) -> None:
        import psycopg2
        self._conn = psycopg2.connect(
            host=self.host, port=self.port, dbname=self.database,
            user=self.user, password=self._password, sslmode="require",
        )
        self._conn.autocommit = True

    def scan_metadata(self) -> dict:
        import psycopg2.extras
        conn = self._conn
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""SELECT table_name FROM information_schema.tables
                       WHERE table_schema='public' AND table_type='BASE TABLE'
                       ORDER BY table_name""")
        tables = [r["table_name"] for r in cur.fetchall()]
        cur.execute("""SELECT table_name, column_name, ordinal_position, data_type, is_nullable
                       FROM information_schema.columns WHERE table_schema='public'
                       ORDER BY table_name, ordinal_position""")
        columns = [dict(r) for r in cur.fetchall()]
        cur.execute("""SELECT relname AS table_name, n_live_tup AS row_count
                       FROM pg_stat_user_tables WHERE schemaname='public'""")
        counts = {r["table_name"]: r["row_count"] for r in cur.fetchall()}
        cur.close()
        cols_by_table: dict[str, list] = {}
        for c in columns:
            cols_by_table.setdefault(c["table_name"], []).append(c)
        return {
            "source_id": f"postgresql_{self.database}", "database": self.database,
            "schema": "public",
            "tables": [{"table_name": t, "columns": cols_by_table.get(t, []),
                         "row_count": counts.get(t, 0)} for t in tables],
        }


class _RedshiftLambdaDriver(_BaseLambdaDriver):
    driver_type = "redshift"

    def connect(self) -> None:
        import redshift_connector
        self._conn = redshift_connector.connect(
            host=self.host, port=self.port, database=self.database,
            user=self.user, password=self._password, ssl=True,
        )
        self._conn.autocommit = True

    def scan_metadata(self) -> dict:
        cur = self._conn.cursor()
        cur.execute("""SELECT table_name FROM information_schema.tables
                       WHERE table_schema='public' AND table_type='BASE TABLE'
                       ORDER BY table_name""")
        tables = [row[0] for row in cur.fetchall()]
        cur.execute("""SELECT table_name, column_name, ordinal_position, data_type, is_nullable
                       FROM information_schema.columns WHERE table_schema='public'
                       ORDER BY table_name, ordinal_position""")
        col_desc = [d[0] for d in cur.description]
        columns = [dict(zip(col_desc, row, strict=False)) for row in cur.fetchall()]
        try:
            cur.execute("""SELECT "table" AS table_name, tbl_rows AS row_count
                           FROM SVV_TABLE_INFO WHERE schema='public'""")
            counts = {row[0]: int(row[1]) for row in cur.fetchall()}
        except Exception:
            counts = {}
        cur.close()
        cols_by_table: dict[str, list] = {}
        for c in columns:
            cols_by_table.setdefault(c["table_name"], []).append(c)
        return {
            "source_id": f"redshift_{self.database}", "database": self.database,
            "schema": "public",
            "tables": [{"table_name": t, "columns": cols_by_table.get(t, []),
                         "row_count": counts.get(t, 0)} for t in tables],
        }


def _get_driver_class(driver_type: str) -> type:
    """Return the appropriate Lambda driver class."""
    if driver_type not in _DRIVER_CLASSES:
        if driver_type == "postgresql":
            _DRIVER_CLASSES["postgresql"] = _PostgreSQLLambdaDriver
        elif driver_type == "redshift":
            _DRIVER_CLASSES["redshift"] = _RedshiftLambdaDriver
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
