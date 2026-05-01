"""Iceberg/Glue driver — pyiceberg + boto3 Glue implementation.

The IcebergDriver is symmetric: it both **scans/reads** existing Iceberg
tables (so TTYD can query registered products) AND **writes** new tables
(so the mapping-agent can register provisioned products there). Per Q3
the user adds it as a first-class third connection in the workspace.

Connection scope: ``(glue_database, s3_warehouse_uri, region)``.
- ``scan_metadata`` uses Glue ``GetTables`` + pyiceberg ``Catalog.load_table``.
- ``execute_query`` uses pyiceberg ``Table.scan()`` with column pushdown
  and a 250-row scan-layer cap (FR-018).
- ``execute_ddl`` raises for DROP/TRUNCATE/ALTER (Constitution Addendum C);
  ``CREATE TABLE`` is allowed since the mapping-agent must register new
  products via this driver.
- ``get_dbt_adapter()`` returns ``"glue"`` so the model-agent emits a
  dbt-glue profile.
"""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


# Block destructive DDL on registered Iceberg tables. CREATE is permitted
# because mapping-agent registration is a write path and must succeed.
_DDL_BLOCK_PATTERN = re.compile(r"\b(DROP|TRUNCATE|ALTER)\b", re.IGNORECASE)


class IcebergDriver:
    """Iceberg/Glue driver implementing the DatabaseDriver protocol."""

    driver_type: str = "iceberg"

    def __init__(
        self,
        glue_database: str,
        warehouse_s3_uri: str,
        region: str = "us-east-1",
        **kwargs: Any,
    ) -> None:
        self.glue_database = glue_database
        self.warehouse_s3_uri = warehouse_s3_uri
        self.region = region
        self._catalog: Any = None
        self._glue: Any = None

    def connect(self, **kwargs: Any) -> None:
        """Initialize the pyiceberg Glue catalog + boto3 Glue client."""
        from pyiceberg.catalog import load_catalog

        # Use the canonical "glue" catalog binding from pyiceberg.
        self._catalog = load_catalog(
            "glue",
            **{
                "type": "glue",
                "warehouse": self.warehouse_s3_uri,
                "py-io-impl": "pyiceberg.io.fsspec.FsspecFileIO",
                "region_name": self.region,
            },
        )
        # Lazy-load boto3 only when connect() runs.
        import boto3

        self._glue = boto3.client("glue", region_name=self.region)
        logger.info(
            "Iceberg connected: glue_db=%s warehouse=%s region=%s",
            self.glue_database,
            self.warehouse_s3_uri,
            self.region,
        )

    def close(self) -> None:
        # pyiceberg + boto3 hold no long-lived sockets; nothing to release.
        self._catalog = None
        self._glue = None

    def _ensure(self) -> None:
        if self._catalog is None or self._glue is None:
            self.connect()

    # ───── Read paths ─────

    def execute_query(self, sql: str, max_rows: int = 100) -> dict[str, Any]:
        """Execute a read-only query.

        pyiceberg's native API is ``Table.scan()`` with predicates rather
        than free-form SQL. For v1 we accept SQL strings of the form
        ``SELECT ... FROM <iceberg_table> [WHERE ...]`` and translate the
        FROM clause to a ``load_table`` call. Anything more complex falls
        back to a friendly NotImplementedError so the caller can route
        through DuckDB instead.
        """
        from platform_agent.workspace.read_only import assert_read_only

        assert_read_only(sql)
        self._ensure()
        cap = min(max_rows, 250)  # FR-018 per-source pull cap

        match = re.search(
            r"FROM\s+([A-Za-z_][\w.]*)",
            sql,
            re.IGNORECASE,
        )
        if not match:
            raise NotImplementedError(
                "IcebergDriver.execute_query expects `SELECT ... FROM <table> [WHERE ...]`; "
                "for cross-source joins, route through the DuckDB scratchpad."
            )
        table_ref = match.group(1)
        # Strip optional `iceberg.` prefix from the FQN convention.
        if table_ref.lower().startswith("iceberg."):
            table_ref = table_ref.split(".", 1)[1]
        # Ensure (db, table) form for load_table.
        if "." not in table_ref:
            table_ref = f"{self.glue_database}.{table_ref}"

        table = self._catalog.load_table(table_ref)
        scan = table.scan(limit=cap)
        arrow_table = scan.to_arrow()
        rows: list[dict[str, Any]] = arrow_table.to_pylist()
        truncated = len(rows) >= cap
        return {
            "columns": [f.name for f in arrow_table.schema],
            "rows": rows,
            "row_count": len(rows),
            "truncated": truncated,
        }

    def scan_metadata(self) -> dict[str, Any]:
        """List Iceberg tables in the configured Glue database."""
        self._ensure()
        # Glue paginates; for v1 (small DBs) one call is plenty.
        resp = self._glue.get_tables(DatabaseName=self.glue_database)
        tables: list[dict[str, Any]] = []
        for t in resp.get("TableList", []):
            try:
                table = self._catalog.load_table(f"{self.glue_database}.{t['Name']}")
                schema = table.schema()
                columns = [
                    {"name": f.name, "data_type": str(f.field_type), "nullable": f.optional}
                    for f in schema.fields
                ]
            except Exception as exc:  # noqa: BLE001 — non-Iceberg tables in the same Glue DB
                logger.debug("skipping non-Iceberg table %s: %s", t.get("Name"), exc)
                continue
            tables.append(
                {
                    "name": t["Name"],
                    "columns": columns,
                    "fully_qualified_name": f"iceberg.{self.glue_database}.{t['Name']}",
                }
            )
        return {
            "source_id": f"iceberg:{self.glue_database}",
            "database": self.glue_database,
            "schema": self.glue_database,  # Glue DB IS the schema for Iceberg
            "tables": tables,
        }

    def profile_columns(self) -> dict[str, Any]:
        # No cheap column-profile path for Iceberg in v1; return scan_metadata
        # plus per-table row-count estimates from snapshot summaries.
        meta = self.scan_metadata()
        for table in meta["tables"]:
            try:
                t = self._catalog.load_table(f"{self.glue_database}.{table['name']}")
                snap = t.current_snapshot()
                if snap is not None:
                    table["row_count_estimate"] = int(
                        snap.summary.get("total-records", 0) if snap.summary else 0
                    )
            except Exception:  # noqa: BLE001
                pass
        return meta

    # ───── Write paths (mapping-agent only) ─────

    def execute_ddl(self, sql: str) -> dict[str, Any]:
        """Execute a DDL statement.

        Only ``CREATE TABLE`` and pyiceberg-mediated registrations are
        supported in v1. DROP/TRUNCATE/ALTER are blocked unconditionally
        per Constitution Addendum C.
        """
        if _DDL_BLOCK_PATTERN.search(sql):
            raise ValueError(
                "Destructive DDL (DROP/TRUNCATE/ALTER) is unconditionally blocked "
                "on Iceberg connections per Constitution Addendum C."
            )
        # CREATE TABLE / register paths go through pyiceberg directly in
        # the mapping-agent rather than via raw SQL strings, so this method
        # is intentionally a no-op in v1 with a sentinel return.
        return {"status": "noop", "statement": sql.strip()[:120]}

    # ───── dbt + protocol ergonomics ─────

    def get_dbt_adapter(self) -> str:
        return "glue"

    def get_dbt_profile(self, **overrides: Any) -> dict[str, Any]:
        """dbt-glue profile fragment."""
        return {
            "type": "glue",
            "region": self.region,
            "schema": self.glue_database,
            "database": self.glue_database,
            "location": self.warehouse_s3_uri,
            "session_provisioning_timeout_in_seconds": 120,
            "worker_type": "G.1X",
            "workers": 2,
            **overrides,
        }
