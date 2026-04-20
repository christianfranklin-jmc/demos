"""Contract tests for POST /workflow/step.

The full routing body lands with T035 in Phase 3. Until then, we assert the
contract we have shipped:

* /health is live.
* /workflow/step 404s (router not registered yet).
* When the router exists, the session-header precondition applies.

T029b extends this file with the memory_unreachable error case once the
router is wired.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from platform_agent.api.app import app


@pytest.fixture
def client():
    # Context-manager form ensures the lifespan (artifact_store sweeper) runs.
    with TestClient(app) as c:
        yield c


def test_health_is_live(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["mode"] in ("local", "deployed")


def test_missing_connection_returns_400(client):
    """Step 1 requires a DB connection (FR-005). Omitting it returns 400."""
    sid = str(uuid4())
    r = client.post(
        "/workflow/step",
        headers={
            "X-DSA-Session-ID": sid,
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        },
        json={
            "step_id": "requirements",
            "user_message": "hi",
            "prior_artifact": None,
            "connection": None,
            "resume": False,
        },
    )
    assert r.status_code == 400
    assert "connection" in r.text.lower()


def test_invalid_step_id_returns_422(client):
    """Unknown step_id is a Pydantic validation error → 422."""
    sid = str(uuid4())
    r = client.post(
        "/workflow/step",
        headers={
            "X-DSA-Session-ID": sid,
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        },
        json={
            "step_id": "not-a-step",
            "user_message": "hi",
            "prior_artifact": None,
            "connection": None,
            "resume": False,
        },
    )
    assert r.status_code == 422


def test_missing_session_header_returns_400(client):
    r = client.post(
        "/workflow/step",
        headers={"Content-Type": "application/json", "Accept": "text/event-stream"},
        json={
            "step_id": "requirements",
            "user_message": "hi",
            "prior_artifact": None,
            "connection": None,
            "resume": False,
        },
    )
    assert r.status_code == 400
    assert "X-DSA-Session-ID" in r.json()["detail"]


def test_artifact_download_unknown_handle_returns_404(client):
    sid = str(uuid4())
    r = client.get(
        f"/workflow/artifact/{uuid4()}",
        headers={"X-DSA-Session-ID": sid},
    )
    assert r.status_code == 404


def test_cancel_unknown_run_returns_cancelled_false(client):
    sid = str(uuid4())
    r = client.post(
        "/workflow/cancel",
        headers={"X-DSA-Session-ID": sid, "Content-Type": "application/json"},
        json={"session_id": sid, "run_id": str(uuid4())},
    )
    assert r.status_code == 200
    assert r.json() == {"cancelled": False}


@pytest.mark.skip(reason="T035: routes_workflow.py not yet implemented")
def test_stream_begins_within_500ms(client):
    """First SSE frame must arrive within 500 ms of a valid request."""
    raise NotImplementedError


@pytest.mark.skip(reason="T035: routes_workflow.py not yet implemented")
def test_terminal_event_closes_stream(client):
    """Every stream ends with exactly one of done / error / artifact_ready."""
    raise NotImplementedError


@pytest.mark.skip(reason="T035: routes_workflow.py not yet implemented (T029b)")
def test_memory_unreachable_surfaces_as_error(client, monkeypatch):
    """When MemoryAdapter raises MemoryUnavailable, route must emit terminal
    ErrorEvent{code: 'memory_unreachable', retriable: true}."""
    raise NotImplementedError


# ── Session-header precondition stays enforceable today since get_session_context
#    is a standalone dep. Reuse the echo pattern from test_session_header.py when
#    writing targeted preconditions against /workflow/* in T035.
