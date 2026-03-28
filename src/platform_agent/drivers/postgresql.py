"""PostgreSQL driver — psycopg2 implementation of DatabaseDriver.

Extracted from the original _toolkit_client.py. Uses information_schema
and pg_stat_user_tables for metadata.
"""

from __future__ import annotations

import logging
from typing import Any

import psycopg2
import psycopg2.extras

logger = logging.getLogger(__name__)


class PostgreSQLDriver:
    """PostgreSQL database driver using psycopg2."""

    driver_type: str = "postgresql"

    def __init__(
        self,
        host: str,
        port: int,
        database: str,
        user: str,
        password: str,
        sslmode: str = "require",
        **kwargs: Any,
    ) -> None:
        self.host = host
        self.port = port
        self.database = database
        self.user = user
        self._password = password
        self._sslmode = sslmode
        self._conn: Any = None

    def connect(self, **kwargs: Any) -> None:
        """Establish the psycopg2 connection."""
        self._conn = psycopg2.connect(
            host=self.host,
            port=self.port,
            dbname=self.database,
            user=self.user,
            password=self._password,
            sslmode=self._sslmode,
        )
        self._conn.autocommit = True
        cur = self._conn.cursor()
        cur.execute("SELECT version()")
        version = cur.fetchone()[0]
        cur.close()
        logger.info("PostgreSQL connected: %s", version)

    def close(self) -> None:
        """Close the psycopg2 connection."""
        if self._conn and not self._conn.closed:
            self._conn.close()

    def _get_conn(self) -> Any:
        """Return (and reconnect if needed) the connection."""
        if self._conn is None or self._conn.closed:
            self.connect()
        return self._conn

    def execute_query(self, sql: str, max_rows: int = 100) -> dict:
        """Execute a read-only SQL query."""
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        normalized = sql.strip().upper()
        for keyword in ("INSERT", "UPDATE", "DELETE", "DROP", "TRUNCATE", "ALTER", "CREATE"):
            if normalized.startswith(keyword):
                raise ValueError(f"Write operations not allowed. SQL starts with {keyword}.")

        cur.execute(sql)

        if cur.description is None:
            cur.close()
            return {"columns": [], "rows": [], "row_count": 0, "truncated": False}

        col_names = [desc[0] for desc in cur.description]
        rows = cur.fetchmany(max_rows)
        row_count = cur.rowcount
        cur.close()

        clean_rows = [{k: _serialize(v) for k, v in dict(row).items()} for row in rows]

        return {
            "columns": col_names,
            "rows": clean_rows,
            "row_count": row_count,
            "truncated": row_count > max_rows,
        }

    def execute_ddl(self, sql: str) -> dict:
        """Execute a DDL statement (DROP/TRUNCATE blocked)."""
        conn = self._get_conn()
        cur = conn.cursor()

        normalized = sql.strip().upper()
        for keyword in ("DROP", "TRUNCATE"):
            if keyword in normalized:
                raise ValueError(f"Destructive DDL blocked: {keyword} is not allowed.")

        cur.execute(sql)
        cur.close()
        return {"status": "success", "statement": sql[:200]}

    def scan_metadata(self) -> dict:
        """Scan metadata via information_schema + pg_stat_user_tables."""
        conn = self._get_conn()
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
                ON tc.constraint_name = kcu.constraint_name
                AND tc.table_schema = kcu.table_schema
            JOIN information_schema.constraint_column_usage ccu
                ON tc.constraint_name = ccu.constraint_name
                AND tc.table_schema = ccu.table_schema
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

        result = {
            "source_id": f"{self.driver_type}_{self.database}",
            "service": self.driver_type,
            "database": self.database,
            "schema": "public",
            "tables": [],
        }

        for tbl in tables:
            name = tbl["table_name"]
            result["tables"].append({
                "table_name": name,
                "columns": columns_by_table.get(name, []),
                "primary_key": pks_by_table.get(name, []),
                "foreign_keys": [fk for fk in fks_list if fk["source_table"] == name],
                "row_count": counts.get(name, 0),
            })

        return result

    def profile_columns(self) -> dict:
        """Profile columns — returns scan data (full profiling requires Toolkit CLI)."""
        result = self.scan_metadata()
        result["_note"] = "Column-level profiling requires phData Toolkit CLI"
        return result

    def get_dbt_adapter(self) -> str:
        return "postgres"

    def get_dbt_profile_config(self) -> dict:
        return {
            "type": "postgres",
            "host": self.host,
            "port": self.port,
            "dbname": self.database,
            "user": self.user,
            "password": self._password,
            "schema": "public",
            "threads": 4,
            "keepalives_idle": 0,
            "sslmode": self._sslmode,
        }


def _serialize(v: Any) -> Any:
    """Convert non-JSON-serializable types to strings."""
    if v is None:
        return None
    if isinstance(v, (int, float, str, bool)):
        return v
    return str(v)
