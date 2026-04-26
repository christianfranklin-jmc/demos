"""MultiSourceDriver — routes scans/queries by `connection_id`.

Holds a registry of :class:`DatabaseDriver` instances keyed by
``connection_id`` and routes ``scan_metadata`` / ``execute_query`` /
``execute_ddl`` to the right child based on a fully-qualified
``source.schema.table`` reference or an explicit ``connection_id``.

Used by:
- Per-connection lifecycle worker (T037) to drive `connect → scan_metadata`.
- TTYD planner (FR-015) to choose a single source vs. multiple.
- DuckDB scratchpad tool (T093) to fan out per-source pulls.

Per Q2 the MultiSourceDriver does **not** unify catalogs across
connections; it is a routing facade, not a federation engine.
"""

from __future__ import annotations

import contextlib
import threading
from typing import Any

from platform_agent.drivers.base import DatabaseDriver
from platform_agent.workspace.read_only import assert_read_only


class UnknownConnectionError(KeyError):
    """Raised when a routing decision references a connection_id we don't hold."""


class MultiSourceDriver:
    """Per-workspace registry of `connection_id → DatabaseDriver`."""

    def __init__(self) -> None:
        self._drivers: dict[str, DatabaseDriver] = {}
        self._lock = threading.RLock()

    def register(self, connection_id: str, driver: DatabaseDriver) -> None:
        with self._lock:
            self._drivers[connection_id] = driver

    def deregister(self, connection_id: str) -> None:
        with self._lock:
            drv = self._drivers.pop(connection_id, None)
        if drv is not None:
            # Best-effort close; some drivers reconnect lazily so close() may no-op.
            with contextlib.suppress(Exception):
                drv.close()

    def get(self, connection_id: str) -> DatabaseDriver:
        with self._lock:
            drv = self._drivers.get(connection_id)
        if drv is None:
            raise UnknownConnectionError(connection_id)
        return drv

    def known(self) -> list[str]:
        with self._lock:
            return list(self._drivers.keys())

    # ───── Routing helpers ─────

    def scan_metadata(self, connection_id: str) -> dict[str, Any]:
        return self.get(connection_id).scan_metadata()

    def execute_query(
        self, connection_id: str, sql: str, max_rows: int = 100
    ) -> dict[str, Any]:
        assert_read_only(sql)
        return self.get(connection_id).execute_query(sql, max_rows=max_rows)

    def route_by_fqn(self, fqn: str, connection_lookup: dict[str, str]) -> DatabaseDriver:
        """Resolve a `<scope>.<schema>.<table>` reference to a driver.

        ``connection_lookup`` maps the leading ``scope`` segment to a
        ``connection_id``; callers (typically the workspace) supply this
        mapping based on each Connection's ``scope`` field.
        """
        head = fqn.split(".", 1)[0]
        connection_id = connection_lookup.get(head)
        if connection_id is None:
            raise UnknownConnectionError(f"no connection for scope `{head}`")
        return self.get(connection_id)
