"""Contract tests for the X-DSA-Session-ID header dependency.

Asserts behavior specified in contracts/session-header.md and ADR-015 D11.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from platform_agent.api.deps import SessionContext, get_session_context
from platform_agent.session import MemoryKey, memory_key_for


@pytest.fixture
def app_with_echo():
    """Minimal app exposing a route that echoes the derived SessionContext."""
    app = FastAPI()

    @app.get("/_echo")
    def echo(session: SessionContext = Depends(get_session_context)):
        return {
            "session_id": str(session.session_id),
            "cognito_sub": session.cognito_sub,
            "mode": session.mode,
        }

    return TestClient(app)


def test_missing_header_returns_400(app_with_echo):
    r = app_with_echo.get("/_echo")
    assert r.status_code == 400
    assert "X-DSA-Session-ID" in r.json()["detail"]


def test_malformed_uuid_returns_400(app_with_echo):
    r = app_with_echo.get("/_echo", headers={"X-DSA-Session-ID": "not-a-uuid"})
    assert r.status_code == 400
    assert "UUID" in r.json()["detail"]


def test_valid_uuid_no_jwt_local_mode(app_with_echo, monkeypatch):
    monkeypatch.delenv("AGENT_MODE", raising=False)
    sid = str(uuid4())
    r = app_with_echo.get("/_echo", headers={"X-DSA-Session-ID": sid})
    assert r.status_code == 200
    body = r.json()
    assert body["session_id"] == sid
    assert body["cognito_sub"] is None
    assert body["mode"] == "local"


def test_deployed_mode_requires_authorization(app_with_echo, monkeypatch):
    monkeypatch.setenv("AGENT_MODE", "deployed")
    sid = str(uuid4())
    r = app_with_echo.get("/_echo", headers={"X-DSA-Session-ID": sid})
    assert r.status_code == 401


def test_memory_key_derivation_local():
    sid = uuid4()
    ctx = SessionContext(session_id=sid, cognito_sub=None, mode="local")
    key = memory_key_for(ctx)
    assert key == MemoryKey(user_scope="local", session_id=str(sid))
    assert key.as_string() == f"dsa:local:{sid}"


def test_memory_key_derivation_deployed():
    sid = uuid4()
    ctx = SessionContext(session_id=sid, cognito_sub="abc123", mode="deployed")
    key = memory_key_for(ctx)
    assert key.as_string() == f"dsa:abc123:{sid}"
