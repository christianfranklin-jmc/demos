"""Database adapter layer using phData Toolkit CLI + psycopg2.

Toolkit CLI handles metadata scanning and profiling (toolkit ds scan/profile).
psycopg2 handles interactive queries and DDL execution (Toolkit ds exec doesn't
return structured result sets).

If Toolkit is not available, falls back to pure psycopg2 for scanning.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
from dataclasses import dataclass, field
from typing import Any

import psycopg2
import psycopg2.extras

logger = logging.getLogger(__name__)

# Module-level session registry (keyed by source_id)
_sessions: dict[str, ToolkitSession] = {}

# Toolkit CLI path — auto-detected or set via environment
TOOLKIT_CLI = os.environ.get(
    "TOOLKIT_CLI",
    os.path.expanduser("~/toolkit-cli-0.90.0/toolkit"),
)


def _toolkit_available() -> bool:
    """Check if the Toolkit CLI is installed and accessible."""
    return os.path.isfile(TOOLKIT_CLI) and os.access(TOOLKIT_CLI, os.X_OK)


def _run_toolkit(args: list[str], project_dir: str | None = None) -> subprocess.CompletedProcess:
    """Run a Toolkit CLI command and return the result."""
    cmd = [TOOLKIT_CLI] + args
    cwd = project_dir or os.getcwd()
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd, timeout=120)
    if result.returncode != 0:
        logger.error("Toolkit CLI failed: %s\nstderr: %s", " ".join(cmd), result.stderr)
        raise RuntimeError(f"Toolkit CLI error: {result.stderr.strip()}")
    return result


@dataclass
class ToolkitSession:
    """Represents an active database connection."""

    source_id: str
    service: str
    host: str
    port: int
    database: str
    user: str
    _password: str = field(repr=False)
    _conn: Any = field(default=None, repr=False)
    project_dir: str = field(default_factory=os.getcwd)

    def get_connection(self) -> Any:
        """Return (and lazily create) the psycopg2 connection."""
        if self._conn is None or self._conn.closed:
            self._conn = psycopg2.connect(
                host=self.host,
                port=self.port,
                dbname=self.database,
                user=self.user,
                password=self._password,
                sslmode="require",
            )
            self._conn.autocommit = True
        return self._conn

    def close(self) -> None:
        if self._conn and not self._conn.closed:
            self._conn.close()


def connect(
    host: str,
    port: int,
    database: str,
    user: str,
    password: str,
    service: str = "rds_postgresql",
    source_id: str | None = None,
) -> ToolkitSession:
    """Establish a connection and register the session."""
    source_id = source_id or f"{service}_{database}"

    session = ToolkitSession(
        source_id=source_id,
        service=service,
        host=host,
        port=port,
        database=database,
        user=user,
        _password=password,
    )

    # Validate connectivity via psycopg2
    conn = session.get_connection()
    cur = conn.cursor()
    cur.execute("SELECT version()")
    version = cur.fetchone()[0]
    cur.close()
    logger.info("Connected to %s: %s", source_id, version)

    _sessions[source_id] = session
    return session


def get_session(source_id: str) -> ToolkitSession:
    """Retrieve a registered session by ID."""
    if source_id not in _sessions:
        available = list(_sessions.keys())
        raise ValueError(f"No session '{source_id}'. Available: {available}")
    return _sessions[source_id]


def scan(source_id: str) -> dict:
    """Scan database metadata using Toolkit CLI if available, else psycopg2.

    Returns Toolkit's structured JSON with ERD graph, tables, columns,
    constraints, and primary keys.
    """
    session = get_session(source_id)

    # Try Toolkit CLI first — it produces richer metadata (ERD graph, constraints)
    if _toolkit_available():
        return _scan_via_toolkit(session)

    # Fallback to psycopg2
    return _scan_via_psycopg2(session)


def profile(source_id: str) -> dict:
    """Profile database using Toolkit CLI (scan + column-level statistics).

    Returns Toolkit's profile JSON with per-column metrics:
    distinct_count, min, max, null_count, etc.
    """
    session = get_session(source_id)

    if _toolkit_available():
        return _profile_via_toolkit(session)

    # Fallback: return scan data (no column metrics without Toolkit)
    result = _scan_via_psycopg2(session)
    result["_note"] = "Column-level profiling requires phData Toolkit CLI"
    return result


def query(source_id: str, sql: str, max_rows: int = 100) -> dict:
    """Execute a read-only SQL query and return structured results."""
    session = get_session(source_id)
    conn = session.get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Block write statements
    normalized = sql.strip().upper()
    for keyword in ("INSERT", "UPDATE", "DELETE", "DROP", "TRUNCATE", "ALTER", "CREATE"):
        if normalized.startswith(keyword):
            raise ValueError(f"Write operations not allowed via query(). SQL starts with {keyword}.")

    cur.execute(sql)

    if cur.description is None:
        cur.close()
        return {"columns": [], "rows": [], "row_count": 0}

    col_names = [desc[0] for desc in cur.description]
    rows = cur.fetchmany(max_rows)
    row_count = cur.rowcount
    cur.close()

    # Convert non-serializable types (dates, decimals) to strings
    clean_rows = []
    for row in rows:
        clean_rows.append({k: _serialize_value(v) for k, v in dict(row).items()})

    return {
        "columns": col_names,
        "rows": clean_rows,
        "row_count": row_count,
        "truncated": row_count > max_rows,
    }


def execute_ddl(source_id: str, sql: str) -> dict:
    """Execute a DDL/write statement. DROP and TRUNCATE are permanently blocked."""
    session = get_session(source_id)
    conn = session.get_connection()
    cur = conn.cursor()

    normalized = sql.strip().upper()
    for keyword in ("DROP", "TRUNCATE"):
        if keyword in normalized:
            raise ValueError(f"Destructive DDL blocked: {keyword} is not allowed.")

    cur.execute(sql)
    cur.close()

    return {"status": "success", "statement": sql[:200]}


# ---------------------------------------------------------------------------
# Toolkit CLI scan/profile implementations
# ---------------------------------------------------------------------------


def _scan_via_toolkit(session: ToolkitSession) -> dict:
    """Run `toolkit ds scan` and return the JSON snapshot."""
    _run_toolkit(["ds", "scan", session.source_id], project_dir=session.project_dir)
    result = _run_toolkit(
        ["ds", "show", f"{session.source_id}:scan:latest", "--format", "JSON"],
        project_dir=session.project_dir,
    )
    # Filter out warning lines (start with ⚠️) before parsing JSON
    json_lines = [line for line in result.stdout.splitlines() if not line.startswith("⚠")]
    return json.loads("\n".join(json_lines))


def _profile_via_toolkit(session: ToolkitSession) -> dict:
    """Run `toolkit ds profile` and return the JSON snapshot."""
    _run_toolkit(["ds", "profile", session.source_id], project_dir=session.project_dir)
    result = _run_toolkit(
        ["ds", "show", f"{session.source_id}:profile:latest", "--format", "JSON"],
        project_dir=session.project_dir,
    )
    json_lines = [line for line in result.stdout.splitlines() if not line.startswith("⚠")]
    return json.loads("\n".join(json_lines))


# ---------------------------------------------------------------------------
# psycopg2 fallback scan
# ---------------------------------------------------------------------------


def _scan_via_psycopg2(session: ToolkitSession) -> dict:
    """Scan metadata using raw information_schema queries."""
    conn = session.get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("""
        SELECT table_schema, table_name, table_type
        FROM information_schema.tables
        WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
        ORDER BY table_name
    """)
    tables = cur.fetchall()

    cur.execute("""
        SELECT table_name, column_name, ordinal_position, data_type,
               character_maximum_length, numeric_precision, is_nullable, column_default
        FROM information_schema.columns
        WHERE table_schema = 'public'
        ORDER BY table_name, ordinal_position
    """)
    columns = cur.fetchall()

    cur.execute("""
        SELECT tc.table_name, kcu.column_name
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
            ON tc.constraint_name = kcu.constraint_name
            AND tc.table_schema = kcu.table_schema
        WHERE tc.constraint_type = 'PRIMARY KEY' AND tc.table_schema = 'public'
        ORDER BY tc.table_name, kcu.ordinal_position
    """)
    pks = cur.fetchall()

    cur.execute("""
        SELECT tc.table_name AS source_table, kcu.column_name AS source_column,
               ccu.table_name AS target_table, ccu.column_name AS target_column
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
            ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema
        JOIN information_schema.constraint_column_usage ccu
            ON tc.constraint_name = ccu.constraint_name AND tc.table_schema = ccu.table_schema
        WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_schema = 'public'
    """)
    fks = cur.fetchall()

    cur.execute("""
        SELECT relname AS table_name, n_live_tup AS row_count
        FROM pg_stat_user_tables WHERE schemaname = 'public'
    """)
    row_counts = cur.fetchall()
    cur.close()

    columns_by_table: dict[str, list] = {}
    for col in columns:
        columns_by_table.setdefault(col["table_name"], []).append(dict(col))

    pks_by_table: dict[str, list] = {}
    for pk in pks:
        pks_by_table.setdefault(pk["table_name"], []).append(pk["column_name"])

    fks_list = [dict(fk) for fk in fks]
    counts = {rc["table_name"]: rc["row_count"] for rc in row_counts}

    profile = {
        "source_id": session.source_id,
        "service": session.service,
        "database": session.database,
        "schema": "public",
        "tables": [],
    }

    for tbl in tables:
        name = tbl["table_name"]
        profile["tables"].append({
            "table_name": name,
            "columns": columns_by_table.get(name, []),
            "primary_key": pks_by_table.get(name, []),
            "foreign_keys": [fk for fk in fks_list if fk["source_table"] == name],
            "row_count": counts.get(name, 0),
        })

    return profile


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _serialize_value(v: Any) -> Any:
    """Convert non-JSON-serializable types to strings."""
    if v is None:
        return None
    if isinstance(v, (int, float, str, bool)):
        return v
    return str(v)
