"""SQLite-backed ConnectionStore — local mode.

One database file per connection at
``~/.dsa-hub/connections/<connection_id>/store.db``. Survives tab close;
each Workspace re-derives the same ``connection_id`` from the user-
supplied (driver, endpoint, scope) tuple and reattaches.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from platform_agent.provisioning.models import IcebergDataProduct, ProductState
from platform_agent.semantic.migrations import apply as apply_migrations
from platform_agent.semantic.models import (
    Domain,
    Join,
    Metric,
    PhysicalBinding,
    SemanticEntity,
)
from platform_agent.workspace.activity_models import ActivityKind, ActivityLogEntry


def _root_dir() -> Path:
    override = os.environ.get("DSA_HUB_CONNECTIONS_DIR")
    if override:
        return Path(override).expanduser()
    return Path.home() / ".dsa-hub" / "connections"


def _store_path(connection_id: str) -> Path:
    base = _root_dir() / connection_id
    base.mkdir(parents=True, exist_ok=True)
    return base / "store.db"


class SQLiteConnectionStore:
    """SQLite implementation of the ConnectionStore Protocol."""

    def __init__(self, *, connection_id: str, path: Path | None = None) -> None:
        self.connection_id = connection_id
        self._path = path or _store_path(connection_id)
        self._conn = sqlite3.connect(self._path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._lock = threading.RLock()
        apply_migrations(self._conn)

    # ───── Semantic graph ─────

    def upsert_entity(self, entity: SemanticEntity) -> None:
        if entity.connection_id != self.connection_id:
            raise ValueError(
                f"entity.connection_id={entity.connection_id} "
                f"does not match store {self.connection_id}"
            )
        with self._lock, self._conn:
            self._conn.execute(
                """
                INSERT INTO entities(
                    entity_id, connection_id, name, domain,
                    payload, version, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(entity_id) DO UPDATE SET
                    name=excluded.name,
                    domain=excluded.domain,
                    payload=excluded.payload,
                    version=excluded.version,
                    updated_at=excluded.updated_at
                """,
                (
                    entity.entity_id,
                    entity.connection_id,
                    entity.name,
                    entity.domain.value,
                    entity.model_dump_json(),
                    entity.version,
                    entity.created_at.isoformat(),
                    entity.updated_at.isoformat(),
                ),
            )

    def get_entity(self, entity_id: str) -> SemanticEntity | None:
        cur = self._conn.execute(
            "SELECT payload FROM entities WHERE entity_id=?", (entity_id,)
        )
        row = cur.fetchone()
        if row is None:
            return None
        return SemanticEntity.model_validate_json(row[0])

    def list_entities(self, *, domain: str | None = None) -> list[SemanticEntity]:
        if domain is not None:
            Domain(domain)  # validates the enum value
            cur = self._conn.execute(
                "SELECT payload FROM entities WHERE domain=? ORDER BY name", (domain,)
            )
        else:
            cur = self._conn.execute("SELECT payload FROM entities ORDER BY name")
        return [SemanticEntity.model_validate_json(r[0]) for r in cur.fetchall()]

    # ───── Physical bindings ─────

    def upsert_binding(self, binding: PhysicalBinding) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                """
                INSERT INTO physical_bindings(binding_id, entity_id, connection_id, fqn, payload)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(binding_id) DO UPDATE SET
                    fqn=excluded.fqn,
                    payload=excluded.payload
                """,
                (
                    binding.binding_id,
                    binding.entity_id,
                    binding.connection_id,
                    binding.fully_qualified_name,
                    binding.model_dump_json(),
                ),
            )

    def list_bindings(self, *, entity_id: str | None = None) -> list[PhysicalBinding]:
        if entity_id is not None:
            cur = self._conn.execute(
                "SELECT payload FROM physical_bindings WHERE entity_id=?", (entity_id,)
            )
        else:
            cur = self._conn.execute("SELECT payload FROM physical_bindings")
        return [PhysicalBinding.model_validate_json(r[0]) for r in cur.fetchall()]

    # ───── Metrics ─────

    def upsert_metric(self, metric: Metric) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                """
                INSERT INTO metrics(metric_id, connection_id, name, payload, version)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(metric_id) DO UPDATE SET
                    name=excluded.name,
                    payload=excluded.payload,
                    version=excluded.version
                """,
                (
                    metric.metric_id,
                    metric.connection_id,
                    metric.name,
                    metric.model_dump_json(),
                    metric.version,
                ),
            )

    def list_metrics(self) -> list[Metric]:
        cur = self._conn.execute("SELECT payload FROM metrics ORDER BY name")
        return [Metric.model_validate_json(r[0]) for r in cur.fetchall()]

    # ───── Joins ─────

    def upsert_join(self, join: Join) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                """
                INSERT INTO joins(
                    join_id, connection_id, left_entity_id, right_entity_id, payload
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(join_id) DO UPDATE SET payload=excluded.payload
                """,
                (
                    join.join_id,
                    join.connection_id,
                    join.left_entity_id,
                    join.right_entity_id,
                    join.model_dump_json(),
                ),
            )

    def list_joins(self) -> list[Join]:
        cur = self._conn.execute("SELECT payload FROM joins")
        return [Join.model_validate_json(r[0]) for r in cur.fetchall()]

    # ───── Iceberg products ─────

    def upsert_product(self, product: IcebergDataProduct) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                """
                INSERT INTO products(
                    product_id, connection_id, table_name, state, ttyd_exposed,
                    payload, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(product_id) DO UPDATE SET
                    table_name=excluded.table_name,
                    state=excluded.state,
                    ttyd_exposed=excluded.ttyd_exposed,
                    payload=excluded.payload,
                    updated_at=excluded.updated_at
                """,
                (
                    product.product_id,
                    product.connection_id,
                    product.table_name,
                    product.state.value,
                    1 if product.ttyd_exposed else 0,
                    product.model_dump_json(),
                    product.created_at.isoformat(),
                    product.updated_at.isoformat(),
                ),
            )
        # Invariant per data-model.md §14: ttyd_exposed iff state == final.
        if product.state == ProductState.FINAL and not product.ttyd_exposed:
            raise ValueError("Invariant violation: state=final must be ttyd_exposed=True")
        if product.state == ProductState.PROVISIONAL and product.ttyd_exposed:
            raise ValueError("Invariant violation: state=provisional must be ttyd_exposed=False")

    def get_product(self, product_id: str) -> IcebergDataProduct | None:
        cur = self._conn.execute("SELECT payload FROM products WHERE product_id=?", (product_id,))
        row = cur.fetchone()
        if row is None:
            return None
        return IcebergDataProduct.model_validate_json(row[0])

    def list_products(self) -> list[IcebergDataProduct]:
        cur = self._conn.execute(
            "SELECT payload FROM products ORDER BY datetime(created_at) DESC"
        )
        return [IcebergDataProduct.model_validate_json(r[0]) for r in cur.fetchall()]

    # ───── Activity log ─────

    def append_activity(self, entry: ActivityLogEntry) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                """
                INSERT INTO activity_log(
                    entry_id, connection_id, workspace_id, kind, payload, ts
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    entry.entry_id,
                    entry.connection_id,
                    str(entry.workspace_id),
                    entry.kind.value,
                    json.dumps(entry.payload),
                    entry.ts.isoformat(),
                ),
            )

    def list_activity(self, *, limit: int = 200) -> list[ActivityLogEntry]:
        # ORDER BY (ts, rowid) DESC so entries with equal timestamps fall back
        # to SQLite insertion order — newest insertion wins.
        cur = self._conn.execute(
            "SELECT entry_id, connection_id, workspace_id, kind, payload, ts "
            "FROM activity_log ORDER BY datetime(ts) DESC, rowid DESC LIMIT ?",
            (limit,),
        )
        out: list[ActivityLogEntry] = []
        for entry_id, conn_id, ws_id, kind, payload, ts in cur.fetchall():
            out.append(
                ActivityLogEntry(
                    entry_id=entry_id,
                    connection_id=conn_id,
                    workspace_id=UUID(ws_id),
                    kind=ActivityKind(kind),
                    payload=json.loads(payload) if payload else {},
                    ts=datetime.fromisoformat(ts),
                )
            )
        return out

    # ───── Discovery cache ─────

    def write_discovery_cache(self, payload: dict[str, Any]) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                """
                INSERT INTO discovery_cache(connection_id, payload, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(connection_id) DO UPDATE SET
                    payload=excluded.payload,
                    updated_at=excluded.updated_at
                """,
                (
                    self.connection_id,
                    json.dumps(payload),
                    datetime.now(tz=UTC).isoformat(),
                ),
            )

    def read_discovery_cache(self) -> dict[str, Any] | None:
        cur = self._conn.execute(
            "SELECT payload FROM discovery_cache WHERE connection_id=?", (self.connection_id,)
        )
        row = cur.fetchone()
        return json.loads(row[0]) if row else None

    def close(self) -> None:
        with self._lock:
            self._conn.close()
