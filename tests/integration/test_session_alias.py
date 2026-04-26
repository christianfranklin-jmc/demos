"""Regression test: X-DSA-Workspace-ID alias does not change behavior (T034).

FR-006: a request with `X-DSA-Session-ID` only routes to the existing
single-source path identically to pre-feature behavior. The new
`X-DSA-Workspace-ID` header is accepted as a synonym for one minor
version and produces the same SessionContext.

Verifies SC-007 invariant for the rename: pre-feature callers that
only send X-DSA-Session-ID continue to work without changes.
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from platform_agent.api.deps import SessionContext, get_session_context


@pytest.fixture
def echo_client() -> TestClient:
    app = FastAPI()

    @app.get("/_echo")
    def echo(
        ctx: SessionContext = Depends(get_session_context),  # noqa: B008
    ) -> dict[str, str]:
        return {"session_id": str(ctx.session_id), "mode": ctx.mode}

    return TestClient(app)


def test_session_id_alone_resolves_unchanged(echo_client: TestClient) -> None:
    """Single-source caller with only X-DSA-Session-ID continues to work."""
    sid = uuid4()
    r = echo_client.get("/_echo", headers={"X-DSA-Session-ID": str(sid)})
    assert r.status_code == 200
    assert r.json()["session_id"] == str(sid)


def test_workspace_id_alias_produces_same_session_context(
    echo_client: TestClient,
) -> None:
    """X-DSA-Workspace-ID alone yields the same SessionContext shape."""
    wid = uuid4()
    r = echo_client.get("/_echo", headers={"X-DSA-Workspace-ID": str(wid)})
    assert r.status_code == 200
    assert r.json()["session_id"] == str(wid)


def test_session_id_takes_precedence_when_both_supplied(
    echo_client: TestClient,
) -> None:
    """If a caller sends both, the canonical X-DSA-Session-ID wins."""
    sid = uuid4()
    wid = uuid4()
    r = echo_client.get(
        "/_echo",
        headers={
            "X-DSA-Session-ID": str(sid),
            "X-DSA-Workspace-ID": str(wid),
        },
    )
    assert r.status_code == 200
    # Returned id matches X-DSA-Session-ID (the canonical header).
    assert UUID(r.json()["session_id"]) == sid


def test_neither_header_returns_400(echo_client: TestClient) -> None:
    r = echo_client.get("/_echo")
    assert r.status_code == 400
    detail = r.json()["detail"]
    assert "X-DSA-Session-ID" in detail
    # Helpful hint includes the alias for migrating callers.
    assert "X-DSA-Workspace-ID" in detail
