"""Lightweight Redshift driver for Lambda — redshift_connector only.

Self-contained (no dependency on src/platform_agent). Mirrors the
DatabaseDriver protocol from src/platform_agent/drivers/base.py.
"""

from __future__ import annotations

import contextlib
import logging
from typing import Any

import redshift_connector

logger = logging.getLogger(__name__)


class RedshiftLambdaDriver:
    driver_type = "redshift"

    def __init__(self, host: str, port: int = 5439, database: str = "dev",
                 user: str = "admin", password: str = "", **kw: Any):
        self.host = host
        self.port = port
        self.database = database
        self.user = user
        self._password = password
        self._conn: Any = None

    def connect(self) -> None:
        self._conn = redshift_connector.connect(
            host=self.host, port=self.port, database=self.database,
            user=self.user, password=self._password, ssl=True,
        )
        self._conn.autocommit = True

    def close(self) -> None:
        if self._conn:
            with contextlib.suppress(Exception):
                self._conn.close()

    def execute_query(self, sql: str, max_rows: int = 100) -> dict:
        cur = self._conn.cursor()
        normalized = sql.strip().upper()
        for kw in ("INSERT", "UPDATE", "DELETE", "DROP", "TRUNCATE", "ALTER", "CREATE"):
            if normalized.startswith(kw):
                raise ValueError(f"Write operations not allowed. SQL starts with {kw}.")
        cur.execute(sql)
        if cur.description is None:
            cur.close()
            return {"columns": [], "rows": [], "row_count": 0, "truncated": False}
        cols = [d[0] for d in cur.description]
        rows = cur.fetchmany(max_rows)
        cur.close()
        return {
            "columns": cols,
            "rows": [{cols[i]: _ser(v) for i, v in enumerate(r)} for r in rows],
            "row_count": len(rows),
            "truncated": len(rows) >= max_rows,
        }

    def execute_ddl(self, sql: str) -> dict:
        normalized = sql.strip().upper()
        for kw in ("DROP", "TRUNCATE"):
            if kw in normalized:
                raise ValueError(f"Destructive DDL blocked: {kw}")
        cur = self._conn.cursor()
        cur.execute(sql)
        cur.close()
        return {"status": "success", "statement": sql[:200]}

    def scan_metadata(self) -> dict:
        cur = self._conn.cursor()

        cur.execute("""
            SELECT table_name FROM information_schema.tables
            WHERE table_schema='public' AND table_type='BASE TABLE' ORDER BY table_name
        """)
        table_names = [r[0] for r in cur.fetchall()]

        cur.execute("""
            SELECT table_name, column_name, ordinal_position, data_type,
                   character_maximum_length, numeric_precision, is_nullable, column_default
            FROM information_schema.columns WHERE table_schema='public'
            ORDER BY table_name, ordinal_position
        """)
        col_desc = [d[0] for d in cur.description]
        columns = [dict(zip(col_desc, r, strict=False)) for r in cur.fetchall()]

        cur.execute("""
            SELECT tc.table_name, kcu.column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
                ON tc.constraint_name=kcu.constraint_name AND tc.table_schema=kcu.table_schema
            WHERE tc.constraint_type='PRIMARY KEY' AND tc.table_schema='public'
        """)
        pk_desc = [d[0] for d in cur.description]
        pks = [dict(zip(pk_desc, r, strict=False)) for r in cur.fetchall()]

        cur.execute("""
            SELECT tc.table_name AS source_table, kcu.column_name AS source_column,
                   ccu.table_name AS target_table, ccu.column_name AS target_column
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
                ON tc.constraint_name=kcu.constraint_name AND tc.table_schema=kcu.table_schema
            JOIN information_schema.constraint_column_usage ccu
                ON tc.constraint_name=ccu.constraint_name AND tc.table_schema=ccu.table_schema
            WHERE tc.constraint_type='FOREIGN KEY' AND tc.table_schema='public'
        """)
        fk_desc = [d[0] for d in cur.description]
        fk_list = [dict(zip(fk_desc, r, strict=False)) for r in cur.fetchall()]

        try:
            cur.execute("""
                SELECT "table" AS table_name, tbl_rows AS row_count
                FROM SVV_TABLE_INFO WHERE schema='public'
            """)
            counts = {r[0]: int(r[1]) for r in cur.fetchall()}
        except Exception:
            counts = {}

        cur.close()

        cols_by: dict[str, list] = {}
        for c in columns:
            cols_by.setdefault(c["table_name"], []).append(c)
        pks_by: dict[str, list] = {}
        for p in pks:
            pks_by.setdefault(p["table_name"], []).append(p["column_name"])

        return {
            "source_id": f"redshift_{self.database}",
            "database": self.database, "schema": "public",
            "tables": [
                {
                    "table_name": t,
                    "columns": cols_by.get(t, []),
                    "primary_key": pks_by.get(t, []),
                    "foreign_keys": [f for f in fk_list if f["source_table"] == t],
                    "row_count": counts.get(t, 0),
                }
                for t in table_names
            ],
        }

    def profile_columns(self) -> dict:
        result = self.scan_metadata()
        result["_note"] = "Column profiling not implemented for Redshift Lambda"
        return result


def _ser(v: Any) -> Any:
    if v is None:
        return None
    if isinstance(v, (int, float, str, bool)):
        return v
    return str(v)
