"""Connection lifecycle worker — drives `connecting → scanning → live` (T037).

Spawned by `routes_workspace.add_connection` and `retry_connection`. Each
tick advances one connection through:

    connecting   -- driver.connect() succeeds  -→ scanning
    scanning     -- driver.scan_metadata() ok  -→ live   (KPIs populated)
    *            -- any exception raised       -→ error  (retryable flag set)

The worker is best-effort: it logs and never raises into FastAPI. Real
driver wiring is feature-gated by env so unit tests can run a fake
sequence without touching live databases (DSA_HUB_LIFECYCLE_FAKE=1).
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import TYPE_CHECKING
from uuid import UUID

from platform_agent.workspace.activity_log import write as log_activity
from platform_agent.workspace.activity_models import ActivityKind
from platform_agent.workspace.models import (
    Connection,
    ConnectionKPIs,
    ConnectionStatus,
    DriverType,
)
from platform_agent.workspace.models import (
    ConnectionError as ConnectionErrorModel,
)
from platform_agent.workspace.registry import get_registry

if TYPE_CHECKING:
    from platform_agent.drivers.base import DatabaseDriver

logger = logging.getLogger(__name__)

# Track in-flight tasks so the test harness can await them cleanly.
_inflight: set[asyncio.Task[None]] = set()


def schedule_connection_lifecycle(
    *, workspace_id: UUID, connection_id: str
) -> asyncio.Task[None] | None:
    """Schedule the lifecycle worker for a connection. Returns the Task.

    If no event loop is running (e.g., synchronous unit-test path), runs
    the lifecycle inline so callers still see a final status.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # No loop running — run inline so the connection still progresses.
        asyncio.run(_run_lifecycle(workspace_id, connection_id))
        return None
    task = loop.create_task(_run_lifecycle(workspace_id, connection_id))
    _inflight.add(task)
    task.add_done_callback(_inflight.discard)
    return task


async def await_inflight() -> None:
    """Test/shutdown helper: wait for every scheduled lifecycle task to finish."""
    if _inflight:
        await asyncio.gather(*list(_inflight), return_exceptions=True)


async def _run_lifecycle(workspace_id: UUID, connection_id: str) -> None:
    registry = get_registry()
    ws = registry.get(workspace_id)
    if ws is None:
        return
    conn = ws.find(connection_id)
    if conn is None:
        return

    fake = os.environ.get("DSA_HUB_LIFECYCLE_FAKE") == "1"

    try:
        # 1. connecting → scanning
        registry.update_connection(
            workspace_id, connection_id, status=ConnectionStatus.SCANNING
        )

        # 2. scanning → live (with KPIs)
        if fake:
            kpis = ConnectionKPIs(tables_total=14, rows_estimated=15415, processes_detected=8)
        else:
            kpis = await _real_scan(conn, workspace_id)

        registry.update_connection(
            workspace_id,
            connection_id,
            status=ConnectionStatus.LIVE,
            kpis=kpis,
            last_synced_at=_now(),
            error=None,
        )
    except Exception as exc:  # noqa: BLE001 — we never want lifecycle to crash the loop
        logger.warning(
            "lifecycle failed for connection %s: %s", connection_id, exc, exc_info=True
        )
        registry.update_connection(
            workspace_id,
            connection_id,
            status=ConnectionStatus.ERROR,
            error=ConnectionErrorModel(
                code="lifecycle_failed",
                message=str(exc),
                retryable=True,
            ),
        )
        log_activity(
            connection_id=connection_id,
            workspace_id=workspace_id,
            kind=ActivityKind.CONNECTION_ERROR,
            payload={"reason": str(exc)},
        )


async def _real_scan(conn: Connection, workspace_id: UUID) -> ConnectionKPIs:
    """Run driver.connect → scan_metadata against the live source.

    Done in a worker thread so blocking driver IO doesn't stall the loop.
    """
    import contextlib

    driver = await asyncio.to_thread(_make_driver, conn, workspace_id)
    try:
        meta = await asyncio.to_thread(driver.scan_metadata)
    finally:
        # Best-effort close; some drivers reconnect lazily.
        with contextlib.suppress(Exception):
            await asyncio.to_thread(driver.close)

    tables = meta.get("tables", []) if isinstance(meta, dict) else []
    return ConnectionKPIs(
        tables_total=len(tables),
        rows_estimated=sum(int(t.get("row_count_estimate") or 0) for t in tables),
        processes_detected=0,  # filled in by US2 discovery, not by raw scan
    )


def _make_driver(conn: Connection, workspace_id: UUID) -> DatabaseDriver:
    """Construct a DatabaseDriver from a Connection + its stashed credentials."""
    # Local import to avoid the routes_workspace ↔ lifecycle cycle.
    from platform_agent.api.routes_workspace import get_credentials
    from platform_agent.drivers import DRIVER_REGISTRY

    creds = get_credentials(workspace_id, conn.connection_id) or {}

    cls = DRIVER_REGISTRY.get(conn.driver_type.value)
    if cls is None:
        raise ValueError(f"No driver registered for {conn.driver_type.value!r}")

    # Drivers vary in their constructor shape. Pass the connection scope/
    # endpoint plus any credentials the user supplied; per-driver kwargs
    # are filtered by the constructor itself.
    kwargs: dict[str, object] = {**creds}
    if conn.driver_type == DriverType.POSTGRESQL:
        host, _, port = conn.endpoint.partition(":")
        kwargs.setdefault("host", host)
        kwargs.setdefault("port", int(port) if port else 5432)
        kwargs.setdefault("database", conn.scope.split(".")[0])
    elif conn.driver_type == DriverType.ICEBERG:
        kwargs.setdefault("glue_database", conn.scope)
        kwargs.setdefault(
            "warehouse_s3_uri", creds.get("warehouse_s3_uri", "s3://placeholder/warehouse")
        )
        kwargs.setdefault("region", creds.get("region", "us-east-1"))

    driver = cls(**kwargs)
    driver.connect()
    return driver


def _now():  # type: ignore[no-untyped-def]
    from datetime import UTC, datetime

    return datetime.now(tz=UTC)
