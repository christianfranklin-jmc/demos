"""Request-scoped in-memory zip store for Step 4 dbt artifact delivery.

Per ADR-015 D10:
  Phase 1: agent produces dbt + semantic layer; server registers a single-use
  60-second UUID handle. Emits `artifact_ready` SSE event.
  Phase 2: frontend issues `GET /workflow/artifact/{handle}`, receives the zip,
  handle is atomically consumed.

No disk persistence; no S3. The store lives on ``app.state.artifact_store`` and
is guarded by an ``asyncio.Lock``. A sweep task drops expired entries every 60 s.
"""

from __future__ import annotations

import asyncio
import contextlib
import io
import logging
import zipfile
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

logger = logging.getLogger(__name__)


HANDLE_TTL = timedelta(seconds=60)
SWEEP_INTERVAL_SECONDS = 60.0


@dataclass(frozen=True, slots=True)
class ArtifactEntry:
    payload: bytes
    expires_at: datetime
    session_id: UUID  # defense-in-depth: GET must carry the same session ID


class ArtifactStore:
    """Async-safe handle store for Step 4 zip payloads."""

    def __init__(self) -> None:
        self._entries: dict[UUID, ArtifactEntry] = {}
        self._lock = asyncio.Lock()
        self._sweep_task: asyncio.Task[None] | None = None

    async def register(self, zip_bytes: bytes, session_id: UUID) -> tuple[UUID, ArtifactEntry]:
        """Store the zip and return (handle, entry)."""
        handle = uuid4()
        entry = ArtifactEntry(
            payload=zip_bytes,
            expires_at=datetime.now(tz=UTC) + HANDLE_TTL,
            session_id=session_id,
        )
        async with self._lock:
            self._entries[handle] = entry
        logger.info("artifact_store.register handle=%s size=%d bytes", handle, len(zip_bytes))
        return handle, entry

    async def consume(self, handle: UUID, session_id: UUID) -> bytes | None:
        """Return the zip and drop the entry; None if unknown/expired/mismatched."""
        async with self._lock:
            entry = self._entries.pop(handle, None)
        if entry is None:
            return None
        if entry.session_id != session_id:
            logger.warning("artifact_store.consume session mismatch handle=%s", handle)
            return None
        if datetime.now(tz=UTC) >= entry.expires_at:
            return None
        return entry.payload

    async def start_sweeper(self) -> None:
        """Start the background sweeper (idempotent)."""
        if self._sweep_task is not None:
            return
        self._sweep_task = asyncio.create_task(self._sweep_loop())

    async def stop_sweeper(self) -> None:
        if self._sweep_task is not None:
            self._sweep_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._sweep_task
            self._sweep_task = None

    async def _sweep_loop(self) -> None:
        while True:
            await asyncio.sleep(SWEEP_INTERVAL_SECONDS)
            await self._sweep_once()

    async def _sweep_once(self) -> None:
        now = datetime.now(tz=UTC)
        async with self._lock:
            expired = [h for h, e in self._entries.items() if e.expires_at <= now]
            for handle in expired:
                self._entries.pop(handle, None)
        if expired:
            logger.info("artifact_store.sweep dropped=%d", len(expired))


def build_zip(files: Mapping[str, bytes | str]) -> bytes:
    """Assemble an in-memory zip from a flat mapping of ``relative_path -> bytes/str``."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path, content in files.items():
            data = content.encode("utf-8") if isinstance(content, str) else content
            zf.writestr(path, data)
    return buffer.getvalue()


__all__ = ["ArtifactEntry", "ArtifactStore", "HANDLE_TTL", "build_zip"]
