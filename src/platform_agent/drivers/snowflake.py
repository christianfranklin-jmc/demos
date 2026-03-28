"""Snowflake driver — snowflake-connector-python implementation of DatabaseDriver.

Uses INFORMATION_SCHEMA for column metadata, SHOW commands for tags and
clustering keys, and TABLES view for row counts. Richer metadata than
PostgreSQL/Redshift drivers — includes Snowflake-specific features like
tags, clustering keys, and object comments.
"""

from __future__ import annotations

import logging
from typing import Any

try:
    import snowflake.connector
except ImportError as err:
    raise ImportError(
        "snowflake-connector-python is required for Snowflake support. "
        "Install with: uv pip install -e '.[snowflake]'"
    ) from err

logger = logging.getLogger(__name__)


class SnowflakeDriver:
    """Snowflake database driver using snowflake-connector-python."""

    driver_type: str = "snowflake"

    def __init__(
        self,
        account: str = "",
        user: str = "",
        password: str = "",
        warehouse: str = "",
        database: str = "",
        schema: str = "PUBLIC",
        role: str = "",
        authenticator: str = "",
        **kwargs: Any,
    ) -> None:
        self.account = account
        self.user = user
        self._password = password
        self.warehouse = warehouse
        self.database = database
        self.schema = schema
        self.role = role
        self.authenticator = authenticator
        self._conn: Any = None
        # Accept host/port for compatibility with driver registry but ignore them
        # Snowflake uses account identifier, not host:port
        self._extra = kwargs

    def connect(self, **kwargs: Any) -> None:
        """Establish the Snowflake connection."""
        connect_params: dict[str, Any] = {
            "account": self.account,
            "user": self.user,
            "warehouse": self.warehouse,
            "database": self.database,
            "schema": self.schema,
        }
        # Support multiple auth methods: password, externalbrowser, keypair
        if self.authenticator:
            connect_params["authenticator"] = self.authenticator
        elif self._password:
            connect_params["password"] = self._password
        if self.role:
            connect_params["role"] = self.role

        self._conn = snowflake.connector.connect(**connect_params)
        cur = self._conn.cursor()
        cur.execute("SELECT CURRENT_VERSION()")
        version = cur.fetchone()[0]
        cur.close()
        logger.info("Snowflake connected: v%s (account=%s)", version, self.account)

    def close(self) -> None:
        """Close the Snowflake connection."""
        if self._conn:
            import contextlib

            with contextlib.suppress(Exception):
                self._conn.close()

    def _get_conn(self) -> Any:
        """Return (and reconnect if needed) the connection."""
        if self._conn is None or self._conn.is_closed():
            self.connect()
        return self._conn

    def execute_query(self, sql: str, max_rows: int = 100) -> dict:
        """Execute a read-only SQL query."""
        conn = self._get_conn()
        cur = conn.cursor(snowflake.connector.DictCursor)

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

        clean_rows = [{k: _serialize(v) for k, v in row.items()} for row in rows]

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
        """Scan metadata via INFORMATION_SCHEMA with Snowflake-specific extras.

        Returns tables, columns, PKs, FKs, row counts, clustering keys,
        and table/column comments (richer than PG/RS drivers).
        """
        conn = self._get_conn()
        cur = conn.cursor(snowflake.connector.DictCursor)

        # Tables with row counts and comments
        cur.execute(f"""
            SELECT TABLE_NAME, TABLE_TYPE, ROW_COUNT, COMMENT
            FROM {self.database}.INFORMATION_SCHEMA.TABLES
            WHERE TABLE_SCHEMA = '{self.schema}'
              AND TABLE_TYPE = 'BASE TABLE'
            ORDER BY TABLE_NAME
        """)
        tables = cur.fetchall()

        # Columns with comments
        cur.execute(f"""
            SELECT TABLE_NAME, COLUMN_NAME, ORDINAL_POSITION, DATA_TYPE,
                   CHARACTER_MAXIMUM_LENGTH, NUMERIC_PRECISION, NUMERIC_SCALE,
                   IS_NULLABLE, COLUMN_DEFAULT, COMMENT
            FROM {self.database}.INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = '{self.schema}'
            ORDER BY TABLE_NAME, ORDINAL_POSITION
        """)
        columns = cur.fetchall()

        # Primary keys
        pks_by_table: dict[str, list[str]] = {}
        try:
            cur.execute(f"SHOW PRIMARY KEYS IN SCHEMA {self.database}.{self.schema}")
            pk_rows = cur.fetchall()
            for pk in pk_rows:
                table_name = pk.get("table_name", pk.get("TABLE_NAME", ""))
                col_name = pk.get("column_name", pk.get("COLUMN_NAME", ""))
                if table_name and col_name:
                    pks_by_table.setdefault(table_name, []).append(col_name)
        except Exception:
            logger.debug("Could not retrieve primary keys (may require OWNERSHIP)")

        # Foreign keys
        fks_list: list[dict] = []
        try:
            cur.execute(
                f"SHOW IMPORTED KEYS IN SCHEMA {self.database}.{self.schema}"
            )
            fk_rows = cur.fetchall()
            for fk in fk_rows:
                fks_list.append({
                    "source_table": fk.get("fk_table_name", fk.get("FK_TABLE_NAME", "")),
                    "source_column": fk.get("fk_column_name", fk.get("FK_COLUMN_NAME", "")),
                    "target_table": fk.get("pk_table_name", fk.get("PK_TABLE_NAME", "")),
                    "target_column": fk.get("pk_column_name", fk.get("PK_COLUMN_NAME", "")),
                })
        except Exception:
            logger.debug("Could not retrieve foreign keys")

        # Clustering keys (Snowflake-specific)
        clustering_by_table: dict[str, str] = {}
        try:
            for tbl in tables:
                tname = tbl.get("TABLE_NAME", "")
                cur.execute(
                    f"SHOW TABLES LIKE '{tname}' IN SCHEMA {self.database}.{self.schema}"
                )
                show_rows = cur.fetchall()
                for row in show_rows:
                    ck = row.get("cluster_by", row.get("CLUSTER_BY", ""))
                    if ck:
                        clustering_by_table[tname] = ck
        except Exception:
            logger.debug("Could not retrieve clustering keys")

        cur.close()

        columns_by_table: dict[str, list] = {}
        for col in columns:
            tname = col.get("TABLE_NAME", "")
            columns_by_table.setdefault(tname, []).append({
                "table_name": tname,
                "column_name": col.get("COLUMN_NAME", ""),
                "ordinal_position": col.get("ORDINAL_POSITION", 0),
                "data_type": col.get("DATA_TYPE", ""),
                "character_maximum_length": col.get("CHARACTER_MAXIMUM_LENGTH"),
                "numeric_precision": col.get("NUMERIC_PRECISION"),
                "numeric_scale": col.get("NUMERIC_SCALE"),
                "is_nullable": col.get("IS_NULLABLE", "YES"),
                "column_default": col.get("COLUMN_DEFAULT"),
                "comment": col.get("COMMENT", ""),
            })

        result: dict[str, Any] = {
            "source_id": f"{self.driver_type}_{self.database}",
            "service": self.driver_type,
            "database": self.database,
            "schema": self.schema,
            "tables": [],
        }

        for tbl in tables:
            name = tbl.get("TABLE_NAME", "")
            table_entry: dict[str, Any] = {
                "table_name": name,
                "columns": columns_by_table.get(name, []),
                "primary_key": pks_by_table.get(name, []),
                "foreign_keys": [fk for fk in fks_list if fk["source_table"] == name],
                "row_count": tbl.get("ROW_COUNT", 0) or 0,
                "comment": tbl.get("COMMENT", ""),
            }
            if name in clustering_by_table:
                table_entry["clustering_key"] = clustering_by_table[name]
            result["tables"].append(table_entry)

        return result

    def profile_columns(self) -> dict:
        """Profile columns — returns scan data with Snowflake comments."""
        result = self.scan_metadata()
        result["_note"] = (
            "Column-level profiling (cardinality, min/max) not yet implemented for Snowflake. "
            "Comments and clustering keys are included in scan metadata."
        )
        return result

    def get_dbt_adapter(self) -> str:
        return "snowflake"

    def get_dbt_profile_config(self) -> dict:
        return {
            "type": "snowflake",
            "account": self.account,
            "user": self.user,
            "password": self._password,
            "warehouse": self.warehouse,
            "database": self.database,
            "schema": self.schema,
            "role": self.role or "PUBLIC",
            "threads": 4,
        }


def _serialize(v: Any) -> Any:
    """Convert non-JSON-serializable types to strings."""
    if v is None:
        return None
    if isinstance(v, (int, float, str, bool)):
        return v
    return str(v)
