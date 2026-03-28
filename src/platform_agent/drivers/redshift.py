"""Redshift driver — redshift_connector implementation of DatabaseDriver.

Uses information_schema for column metadata and SVV_TABLE_INFO for row counts.
Redshift is PostgreSQL-based but has its own system views and connector.
"""

from __future__ import annotations

import logging
from typing import Any

try:
    import redshift_connector
except ImportError as err:
    raise ImportError(
        "redshift_connector is required for Redshift support. "
        "Install with: uv pip install -e '.[redshift]'"
    ) from err

logger = logging.getLogger(__name__)


class RedshiftDriver:
    """Amazon Redshift database driver using redshift_connector."""

    driver_type: str = "redshift"

    def __init__(
        self,
        host: str,
        port: int = 5439,
        database: str = "dev",
        user: str = "admin",
        password: str = "",
        ssl: bool = True,
        **kwargs: Any,
    ) -> None:
        self.host = host
        self.port = port
        self.database = database
        self.user = user
        self._password = password
        self._ssl = ssl
        self._conn: Any = None

    def connect(self, **kwargs: Any) -> None:
        """Establish the Redshift connection."""
        self._conn = redshift_connector.connect(
            host=self.host,
            port=self.port,
            database=self.database,
            user=self.user,
            password=self._password,
            ssl=self._ssl,
        )
        self._conn.autocommit = True
        cur = self._conn.cursor()
        cur.execute("SELECT version()")
        version = cur.fetchone()[0]
        cur.close()
        logger.info("Redshift connected: %s", version)

    def close(self) -> None:
        """Close the Redshift connection."""
        if self._conn:
            import contextlib
            with contextlib.suppress(Exception):
                self._conn.close()

    def _get_conn(self) -> Any:
        """Return (and reconnect if needed) the connection."""
        if self._conn is None:
            self.connect()
        return self._conn

    def execute_query(self, sql: str, max_rows: int = 100) -> dict:
        """Execute a read-only SQL query."""
        conn = self._get_conn()
        cur = conn.cursor()

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
        row_count = len(rows)
        cur.close()

        clean_rows = [
            {col_names[i]: _serialize(v) for i, v in enumerate(row)}
            for row in rows
        ]

        return {
            "columns": col_names,
            "rows": clean_rows,
            "row_count": row_count,
            "truncated": row_count >= max_rows,
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
        """Scan metadata via information_schema + SVV_TABLE_INFO."""
        conn = self._get_conn()
        cur = conn.cursor()

        # Tables
        cur.execute("""
            SELECT table_schema, table_name, table_type
            FROM information_schema.tables
            WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
            ORDER BY table_name
        """)
        tables = cur.fetchall()
        table_cols = [desc[0] for desc in cur.description]
        tables = [dict(zip(table_cols, row, strict=False)) for row in tables]

        # Columns
        cur.execute("""
            SELECT table_name, column_name, ordinal_position, data_type,
                   character_maximum_length, numeric_precision, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_schema = 'public'
            ORDER BY table_name, ordinal_position
        """)
        col_desc = [desc[0] for desc in cur.description]
        columns = [dict(zip(col_desc, row, strict=False)) for row in cur.fetchall()]

        # Primary keys (Redshift doesn't enforce but may declare)
        cur.execute("""
            SELECT tc.table_name, kcu.column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
                ON tc.constraint_name = kcu.constraint_name
                AND tc.table_schema = kcu.table_schema
            WHERE tc.constraint_type = 'PRIMARY KEY' AND tc.table_schema = 'public'
            ORDER BY tc.table_name, kcu.ordinal_position
        """)
        pk_desc = [desc[0] for desc in cur.description]
        pks = [dict(zip(pk_desc, row, strict=False)) for row in cur.fetchall()]

        # Foreign keys
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
        fk_desc = [desc[0] for desc in cur.description]
        fks_list = [dict(zip(fk_desc, row, strict=False)) for row in cur.fetchall()]

        # Row counts via SVV_TABLE_INFO (Redshift-specific, more accurate)
        try:
            cur.execute("""
                SELECT "table" AS table_name, tbl_rows AS row_count
                FROM SVV_TABLE_INFO
                WHERE schema = 'public'
            """)
            row_counts = {row[0]: int(row[1]) for row in cur.fetchall()}
        except Exception:
            # Fallback if SVV_TABLE_INFO is not accessible
            row_counts = {}

        cur.close()

        columns_by_table: dict[str, list] = {}
        for col in columns:
            columns_by_table.setdefault(col["table_name"], []).append(col)

        pks_by_table: dict[str, list] = {}
        for pk in pks:
            pks_by_table.setdefault(pk["table_name"], []).append(pk["column_name"])

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
                "row_count": row_counts.get(name, 0),
            })

        return result

    def profile_columns(self) -> dict:
        """Profile columns — basic scan data for Redshift."""
        result = self.scan_metadata()
        result["_note"] = "Column-level profiling not yet implemented for Redshift"
        return result

    def get_dbt_adapter(self) -> str:
        return "redshift"

    def get_dbt_profile_config(self) -> dict:
        return {
            "type": "redshift",
            "host": self.host,
            "port": self.port,
            "dbname": self.database,
            "user": self.user,
            "password": self._password,
            "schema": "public",
            "threads": 4,
        }


def _serialize(v: Any) -> Any:
    """Convert non-JSON-serializable types to strings."""
    if v is None:
        return None
    if isinstance(v, (int, float, str, bool)):
        return v
    return str(v)
