"""Shared fixtures for Phase 3 integration tests.

All DB-backed tests are env-gated: if the environment does not advertise a
live source (DB_HOST / SF_ACCOUNT / RS_HOST), the dependent test is skipped
rather than failing. This matches SC-005 and SC-006's intent and lets the
suite run cleanly on a laptop with no AWS access.
"""

from __future__ import annotations

import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from platform_agent.api.app import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def session_id() -> str:
    """Unique per-test session UUID."""
    return str(uuid4())


@pytest.fixture
def session_headers(session_id: str) -> dict[str, str]:
    return {
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
        "X-DSA-Session-ID": session_id,
    }


@pytest.fixture
def northwinds_postgres_connection() -> dict | None:
    """Build a PostgreSQL connection payload for Northwinds, or None if unset."""
    host = os.environ.get("DB_HOST")
    if not host or host.startswith("platform-agent-northwinds.XXXX"):
        return None
    return {
        "driver_type": "postgresql",
        "host": host,
        "port": int(os.environ.get("DB_PORT", "5432")),
        "database": os.environ.get("DB_NAME", "northwinds"),
        "schema": "public",
        "user": os.environ.get("DB_USER", "postgres"),
        "credential": {
            "kind": "password",
            "password": os.environ.get("DB_PASSWORD", ""),
        },
    }


@pytest.fixture
def pinnacle_snowflake_connection() -> dict | None:
    """Build a Snowflake SSO connection payload, or None if SF_ACCOUNT unset."""
    account = os.environ.get("SF_ACCOUNT")
    if not account:
        return None
    return {
        "driver_type": "snowflake",
        "account": account,
        "database": os.environ.get("SF_DATABASE", "PINNACLE_FINANCIAL_DEMO_ASINGH"),
        "schema": os.environ.get("SF_SCHEMA", "ANALYTICS"),
        "user": os.environ.get("SF_USER", ""),
        "role": os.environ.get("SF_ROLE"),
        "warehouse": os.environ.get("SF_WAREHOUSE"),
        "credential": {"kind": "sso_externalbrowser"},
    }


@pytest.fixture
def redshift_connection() -> dict | None:
    host = os.environ.get("RS_HOST")
    if not host or host.startswith("platform-agent-wg.XXXX"):
        return None
    return {
        "driver_type": "redshift",
        "host": host,
        "port": int(os.environ.get("RS_PORT", "5439")),
        "database": os.environ.get("RS_DATABASE", "dev"),
        "user": os.environ.get("RS_USER", "admin"),
        "credential": {"kind": "password", "password": os.environ.get("RS_PASSWORD", "")},
    }


def parse_sse_stream(text: str) -> list[dict]:
    """Split a raw SSE body into a list of {event, data} dicts."""
    import json

    frames: list[dict] = []
    for block in text.split("\n\n"):
        if not block.strip():
            continue
        event = "message"
        data_lines: list[str] = []
        for line in block.split("\n"):
            if line.startswith("event:"):
                event = line[len("event:") :].strip()
            elif line.startswith("data:"):
                data_lines.append(line[len("data:") :].lstrip())
        frames.append({"event": event, "data": json.loads("\n".join(data_lines))})
    return frames
