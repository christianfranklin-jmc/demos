"""SSE emitter with dual-layer keepalive (ADR-015 D9).

- Passive: emits :class:`HeartbeatEvent` every 10 s when the queue has been idle.
- Active: tools call :func:`emit_tool_progress` via the :data:`heartbeat_emitter`
  ContextVar at natural progress boundaries.

Every event is formatted as ``event: <name>\\ndata: <json>\\n\\n``. The async
generator closes after a terminal event (done / error / artifact_ready) is sent.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator, Callable
from contextvars import ContextVar
from uuid import UUID

from .events import (
    HeartbeatEvent,
    ToolProgressEvent,
    _EventBase,
    event_name,
    is_terminal,
)

logger = logging.getLogger(__name__)

# ContextVar set by SSEEmitter when a request begins; tool wrappers call it
# at progress boundaries. None = no active emitter (CLI / Streamlit paths).
heartbeat_emitter: ContextVar[Callable[[ToolProgressEvent], None] | None] = ContextVar(
    "heartbeat_emitter", default=None
)


HEARTBEAT_IDLE_SECONDS = 10.0


class SSEEmitter:
    """Queue-backed SSE event emitter.

    Usage from a FastAPI route::

        emitter = SSEEmitter()
        asyncio.create_task(run_step(request, session, emitter))
        return StreamingResponse(emitter.stream(), media_type="text/event-stream")
    """

    def __init__(self) -> None:
        self._queue: asyncio.Queue[_EventBase] = asyncio.Queue()
        self._closed = asyncio.Event()

    def emit(self, event: _EventBase) -> None:
        """Synchronously enqueue an event. Non-blocking — the queue is unbounded."""
        if self._closed.is_set():
            logger.warning("SSEEmitter: emit after close — dropping %s", type(event).__name__)
            return
        self._queue.put_nowait(event)

    def close(self) -> None:
        """Mark the stream closed (caller has emitted a terminal event)."""
        self._closed.set()

    async def stream(self) -> AsyncIterator[bytes]:
        """Yield formatted SSE frames. Emits passive heartbeats while idle."""
        # Open with an immediate heartbeat so the client's silence timer has a baseline.
        yield self._format(HeartbeatEvent())

        while True:
            try:
                event = await asyncio.wait_for(self._queue.get(), timeout=HEARTBEAT_IDLE_SECONDS)
            except TimeoutError:
                if self._closed.is_set() and self._queue.empty():
                    break
                yield self._format(HeartbeatEvent())
                continue

            yield self._format(event)
            if is_terminal(event):
                break

    @staticmethod
    def _format(event: _EventBase) -> bytes:
        name = event_name(event)
        payload = event.model_dump(mode="json")
        return f"event: {name}\ndata: {json.dumps(payload, default=str)}\n\n".encode()


def make_progress_emitter(
    emitter: SSEEmitter, run_id: UUID
) -> Callable[[ToolProgressEvent], None]:
    """Return a callable tools can invoke via the heartbeat_emitter ContextVar.

    Ensures the run_id is stamped correctly even if tools forget to set it.
    """

    def _emit(event: ToolProgressEvent) -> None:
        if event.run_id != run_id:
            event = event.model_copy(update={"run_id": run_id})
        emitter.emit(event)

    return _emit


__all__ = ["SSEEmitter", "heartbeat_emitter", "make_progress_emitter", "HEARTBEAT_IDLE_SECONDS"]
