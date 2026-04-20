"""T034: Keepalive-driven timeout contract (FR-023, Clarify Q5).

Instead of spinning up the full workflow router (which requires a live
database), this test exercises the passive heartbeat + silence-timeout
machinery in isolation:

* SSEEmitter emits a heartbeat every 10 s while idle.
* After 30 s of total silence (no events at all), the caller is expected to
  treat the stream as a failure.

We assert the emitter's behavior directly by consuming the stream generator
with a compressed clock (monkey-patched sleep) rather than waiting 30 s of
wall time.
"""

from __future__ import annotations

import asyncio
import json
from uuid import uuid4

import pytest

from platform_agent.api.events import DoneEvent, ToolProgressEvent
from platform_agent.api.sse import SSEEmitter, make_progress_emitter


def _decode(frame: bytes) -> dict:
    lines = frame.decode("utf-8").strip().split("\n")
    event = next(l.split(":", 1)[1].strip() for l in lines if l.startswith("event:"))
    data = next(l.split(":", 1)[1].strip() for l in lines if l.startswith("data:"))
    return {"event": event, "data": json.loads(data)}


@pytest.mark.asyncio
async def test_heartbeat_emits_on_idle(monkeypatch):
    """With no active events, the emitter produces a heartbeat on the 10s tick."""
    # Compress the 10s idle timeout to something tests can tolerate.
    monkeypatch.setattr("platform_agent.api.sse.HEARTBEAT_IDLE_SECONDS", 0.05)

    emitter = SSEEmitter()
    stream = emitter.stream()

    # First frame is the baseline heartbeat.
    first = await asyncio.wait_for(stream.__anext__(), timeout=1.0)
    assert _decode(first)["event"] == "heartbeat"

    # Second frame must also be a heartbeat (idle timeout fired).
    second = await asyncio.wait_for(stream.__anext__(), timeout=1.0)
    assert _decode(second)["event"] == "heartbeat"

    # Close the stream cleanly.
    emitter.close()


@pytest.mark.asyncio
async def test_progress_event_resets_silence(monkeypatch):
    """Tool progress events interrupt idle heartbeats and flow to the client."""
    monkeypatch.setattr("platform_agent.api.sse.HEARTBEAT_IDLE_SECONDS", 0.5)

    emitter = SSEEmitter()
    stream = emitter.stream()
    run_id = uuid4()
    push = make_progress_emitter(emitter, run_id)

    # Baseline heartbeat.
    baseline = await asyncio.wait_for(stream.__anext__(), timeout=1.0)
    assert _decode(baseline)["event"] == "heartbeat"

    # Emit a progress event before the idle-heartbeat would fire.
    push(ToolProgressEvent(run_id=run_id, tool="scan_metadata", note="tick"))
    progress = await asyncio.wait_for(stream.__anext__(), timeout=1.0)
    decoded = _decode(progress)
    assert decoded["event"] == "tool_progress"
    assert decoded["data"]["note"] == "tick"

    emitter.close()


@pytest.mark.asyncio
async def test_terminal_event_closes_stream():
    """A DoneEvent causes the generator to stop yielding."""
    emitter = SSEEmitter()
    run_id = uuid4()
    emitter.emit(DoneEvent(run_id=run_id, step="requirements"))
    emitter.close()

    stream = emitter.stream()
    frames: list[bytes] = []
    async for frame in stream:
        frames.append(frame)

    # Expect: [baseline heartbeat, done]. No frames after 'done'.
    events = [_decode(f)["event"] for f in frames]
    assert "done" in events
    assert events[-1] == "done"
