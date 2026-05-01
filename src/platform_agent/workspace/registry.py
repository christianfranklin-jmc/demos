"""Per-tab workspace registry (in-memory).

A :class:`WorkspaceRegistry` keys :class:`Workspace` records by the
per-tab session UUID (Q1). Thread-safe via a single lock; sized for a
single agent backend process serving many tabs concurrently. State is
lost on process restart by design — durable assets live in per-connection
stores instead (research.md R2).
"""

from __future__ import annotations

import threading
from datetime import UTC, datetime
from uuid import UUID

from platform_agent.workspace.models import Connection, Workspace


class WorkspaceRegistry:
    """Process-wide, thread-safe map of session UUID → Workspace."""

    def __init__(self) -> None:
        self._workspaces: dict[UUID, Workspace] = {}
        self._lock = threading.RLock()

    def get_or_create(self, workspace_id: UUID) -> Workspace:
        with self._lock:
            ws = self._workspaces.get(workspace_id)
            if ws is None:
                ws = Workspace(
                    workspace_id=workspace_id,
                    created_at=datetime.now(tz=UTC),
                )
                self._workspaces[workspace_id] = ws
            return ws

    def get(self, workspace_id: UUID) -> Workspace | None:
        with self._lock:
            return self._workspaces.get(workspace_id)

    def add_connection(self, workspace_id: UUID, connection: Connection) -> Connection:
        """Append a connection to a workspace, deduping on (driver, endpoint, scope).

        Returns the existing record if a duplicate exists.
        """
        with self._lock:
            ws = self.get_or_create(workspace_id)
            existing = ws.find(connection.connection_id)
            if existing is not None:
                return existing
            ws.connections.append(connection)
            return connection

    def remove_connection(self, workspace_id: UUID, connection_id: str) -> bool:
        with self._lock:
            ws = self.get(workspace_id)
            if ws is None:
                return False
            before = len(ws.connections)
            ws.connections = [c for c in ws.connections if c.connection_id != connection_id]
            return len(ws.connections) < before

    def update_connection(
        self, workspace_id: UUID, connection_id: str, **fields: object
    ) -> Connection | None:
        with self._lock:
            ws = self.get(workspace_id)
            if ws is None:
                return None
            for i, c in enumerate(ws.connections):
                if c.connection_id == connection_id:
                    updated = c.model_copy(update=fields)
                    ws.connections[i] = updated
                    return updated
            return None

    def discard(self, workspace_id: UUID) -> bool:
        with self._lock:
            return self._workspaces.pop(workspace_id, None) is not None


_registry: WorkspaceRegistry | None = None
_registry_lock = threading.Lock()


def get_registry() -> WorkspaceRegistry:
    """Process-wide singleton accessor."""
    global _registry
    if _registry is None:
        with _registry_lock:
            if _registry is None:
                _registry = WorkspaceRegistry()
    return _registry
