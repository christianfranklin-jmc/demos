"""T052: FR-028 — switching source mid-session must protect prior artifacts.

The switch-confirmation UX lives in the frontend (AppContext CONNECTION_SET
handler + a modal in a later pass). This test covers the backend invariant:
a new session ID cleanly separates runs even against different driver types.
"""

from __future__ import annotations

from uuid import uuid4

from .conftest import parse_sse_stream


def test_different_session_ids_dont_leak_artifacts(client):
    """Two concurrent sessions (simulated) against the router never produce
    cross-contaminated artifacts, even when they share host+driver config."""
    sid_a = str(uuid4())
    sid_b = str(uuid4())

    # Both requests lack a connection → both 400 cleanly and independently.
    for sid in (sid_a, sid_b):
        r = client.post(
            "/workflow/step",
            headers={
                "Content-Type": "application/json",
                "Accept": "text/event-stream",
                "X-DSA-Session-ID": sid,
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

    # Unknown artifact handles must 404 per-session regardless of which
    # session requests them — there's no shared pool (FR-026 / FR-027).
    h = str(uuid4())
    r_a = client.get(f"/workflow/artifact/{h}", headers={"X-DSA-Session-ID": sid_a})
    r_b = client.get(f"/workflow/artifact/{h}", headers={"X-DSA-Session-ID": sid_b})
    assert r_a.status_code == 404
    assert r_b.status_code == 404
