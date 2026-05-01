"""SQLite schema migrations for SQLiteConnectionStore.

Migrations are idempotent SQL scripts applied in order on first open.
The current schema version is recorded in the ``schema_meta`` table.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence

# Schema migrations as inline SQL keeps the runtime dependency-free.
# Each migration is a list of statements run in a single transaction.

_MIGRATIONS: Sequence[tuple[int, list[str]]] = (
    (
        1,
        [
            """
            CREATE TABLE IF NOT EXISTS schema_meta (
                version INTEGER PRIMARY KEY,
                applied_at TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS entities (
                entity_id TEXT PRIMARY KEY,
                connection_id TEXT NOT NULL,
                name TEXT NOT NULL,
                domain TEXT NOT NULL,
                payload TEXT NOT NULL,
                version INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_entities_name ON entities(name)",
            "CREATE INDEX IF NOT EXISTS idx_entities_domain ON entities(domain)",
            """
            CREATE TABLE IF NOT EXISTS physical_bindings (
                binding_id TEXT PRIMARY KEY,
                entity_id TEXT NOT NULL,
                connection_id TEXT NOT NULL,
                fqn TEXT NOT NULL,
                payload TEXT NOT NULL,
                FOREIGN KEY (entity_id) REFERENCES entities(entity_id)
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_bindings_entity ON physical_bindings(entity_id)",
            """
            CREATE TABLE IF NOT EXISTS metrics (
                metric_id TEXT PRIMARY KEY,
                connection_id TEXT NOT NULL,
                name TEXT NOT NULL,
                payload TEXT NOT NULL,
                version INTEGER NOT NULL DEFAULT 1
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_metrics_name ON metrics(name)",
            """
            CREATE TABLE IF NOT EXISTS joins (
                join_id TEXT PRIMARY KEY,
                connection_id TEXT NOT NULL,
                left_entity_id TEXT NOT NULL,
                right_entity_id TEXT NOT NULL,
                payload TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS products (
                product_id TEXT PRIMARY KEY,
                connection_id TEXT NOT NULL,
                table_name TEXT NOT NULL,
                state TEXT NOT NULL,
                ttyd_exposed INTEGER NOT NULL DEFAULT 0,
                payload TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_products_state ON products(state)",
            """
            CREATE TABLE IF NOT EXISTS activity_log (
                entry_id TEXT PRIMARY KEY,
                connection_id TEXT NOT NULL,
                workspace_id TEXT NOT NULL,
                kind TEXT NOT NULL,
                payload TEXT NOT NULL,
                ts TEXT NOT NULL
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_activity_ts ON activity_log(ts)",
            """
            CREATE TABLE IF NOT EXISTS discovery_cache (
                connection_id TEXT PRIMARY KEY,
                payload TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """,
        ],
    ),
)


def apply(conn: sqlite3.Connection) -> int:
    """Apply pending migrations; return the resulting schema version."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_meta (
            version INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL
        )
        """
    )
    cur = conn.execute("SELECT MAX(version) FROM schema_meta")
    row = cur.fetchone()
    current = int(row[0]) if row and row[0] is not None else 0

    from datetime import UTC, datetime

    target = current
    for version, statements in _MIGRATIONS:
        if version <= current:
            continue
        with conn:
            for stmt in statements:
                conn.execute(stmt)
            conn.execute(
                "INSERT OR REPLACE INTO schema_meta(version, applied_at) VALUES (?, ?)",
                (version, datetime.now(tz=UTC).isoformat()),
            )
        target = version
    return target
