"""Activity-log writer — append-only audit chain (FR-032, SC-008).

The workspace activity log captures every step of the workflow chain
(discovery → pill click → PRD → redundancy decision → provisioning →
validation) so an audit reviewer can reconstruct a run from the log
alone. Entries are written through the connection's durable store and
NEVER raised into the caller — log-and-drop on store failures so
user-flow invariants are preserved.

The store layer is added in T019/T020. Until then this module emits to
the standard logger and buffers on a process-local list so callers can
exercise the API ahead of the store landing.
"""

from __future__ import annotations

import logging
import threading
import uuid
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from platform_agent.workspace.activity_models import ActivityKind, ActivityLogEntry

logger = logging.getLogger(__name__)


class _Buffer:
    """Process-local fallback when no durable store is wired yet."""

    def __init__(self) -> None:
        self._entries: list[ActivityLogEntry] = []
        self._lock = threading.Lock()

    def append(self, entry: ActivityLogEntry) -> None:
        with self._lock:
            self._entries.append(entry)

    def snapshot(self) -> list[ActivityLogEntry]:
        with self._lock:
            return list(self._entries)


_buffer = _Buffer()


def write(
    *,
    connection_id: str,
    workspace_id: UUID,
    kind: ActivityKind,
    payload: dict[str, Any] | None = None,
) -> ActivityLogEntry:
    """Append an entry. Never raises; logs+drops on failure."""
    entry = ActivityLogEntry(
        entry_id=str(uuid.uuid4()),
        connection_id=connection_id,
        workspace_id=workspace_id,
        kind=kind,
        payload=payload or {},
        ts=datetime.now(tz=UTC),
    )
    try:
        _buffer.append(entry)
        # TODO(T020): also write to ConnectionStore once the store lands.
        logger.debug(
            "activity_log: %s connection=%s ws=%s",
            kind.value,
            connection_id,
            workspace_id,
        )
    except Exception as exc:  # noqa: BLE001 — never raise into the caller
        logger.warning("activity_log write failed (dropped): %s", exc)
    return entry


def snapshot() -> list[ActivityLogEntry]:
    """Process-local snapshot (test/debug aid; durable read goes via the store)."""
    return _buffer.snapshot()
