"""End-to-end happy-path test using a mock driver.

This test exercises the full SSE pipeline: router → step handler → driver
layer → Pydantic event emission → SSE framing → response parsing. It
replaces psycopg2 with an in-memory fake so the test runs with no AWS or
DB dependencies while still proving the wire actually works.

If this test passes, the only thing a live Northwinds test verifies beyond
what we already cover here is that the real psycopg2 driver can open a
real TCP socket — which is tested by the driver package upstream.
"""

from __future__ import annotations

import io
import zipfile
from typing import Any

import pytest

from platform_agent.drivers import DRIVER_REGISTRY

from .conftest import parse_sse_stream

MOCK_SCHEMA = {
    "tables": [
        {
            "name": "orders",
            "primary_keys": ["order_id"],
            "row_count": 830,
            "columns": [
                {"name": "order_id", "data_type": "integer", "nullable": False},
                {"name": "customer_id", "data_type": "varchar", "nullable": False},
                {"name": "order_date", "data_type": "date", "nullable": False},
                {"name": "freight", "data_type": "numeric", "nullable": True},
            ],
        },
        {
            "name": "customers",
            "primary_keys": ["customer_id"],
            "row_count": 91,
            "columns": [
                {"name": "customer_id", "data_type": "varchar", "nullable": False},
                {"name": "company_name", "data_type": "varchar", "nullable": False},
                {"name": "country", "data_type": "varchar", "nullable": True},
            ],
        },
        {
            "name": "products",
            "primary_keys": ["product_id"],
            "row_count": 77,
            "columns": [
                {"name": "product_id", "data_type": "integer", "nullable": False},
                {"name": "product_name", "data_type": "varchar", "nullable": False},
                {"name": "unit_price", "data_type": "numeric", "nullable": True},
            ],
        },
    ],
    "foreign_keys": [
        {
            "from_table": "orders",
            "to_table": "customers",
            "from_column": "customer_id",
            "to_column": "customer_id",
        },
    ],
}


class MockDriver:
    """In-memory stand-in for psycopg2 / redshift_connector / snowflake.

    Matches the DatabaseDriver protocol: `connect()`, `scan_metadata()`,
    `profile_columns()`, `run_query()`, `get_dbt_adapter()`.
    """

    driver_type = "postgresql"

    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs

    def connect(self) -> None:
        """No-op for the mock — no real socket to open."""

    def scan_metadata(self) -> dict[str, Any]:
        return MOCK_SCHEMA

    def profile_columns(self) -> dict[str, Any]:
        return {"tables": [t["name"] for t in MOCK_SCHEMA["tables"]]}

    def run_query(self, sql: str) -> dict[str, Any]:
        return {"rows": [("sample1",), ("sample2",), ("sample3",)]}

    def get_dbt_adapter(self) -> str:
        return "postgres"


@pytest.fixture
def mock_driver():
    """Replace the postgresql driver in DRIVER_REGISTRY for the duration of a test."""
    from platform_agent import drivers

    original = DRIVER_REGISTRY.get("postgresql")
    DRIVER_REGISTRY["postgresql"] = MockDriver  # type: ignore[assignment]
    drivers._drivers.clear()  # start with no cached driver instances

    yield

    drivers._drivers.clear()
    if original is not None:
        DRIVER_REGISTRY["postgresql"] = original


def _connection_payload() -> dict:
    return {
        "driver_type": "postgresql",
        "host": "mock-host",
        "port": 5432,
        "database": "northwinds_mock",
        "schema": "public",
        "user": "mockuser",
        "credential": {"kind": "password", "password": "mockpass"},
    }


def test_step_1_full_pipeline(client, session_headers, mock_driver):
    response = client.post(
        "/workflow/step",
        headers=session_headers,
        json={
            "step_id": "requirements",
            "user_message": "Help me understand our orders data.",
            "prior_artifact": None,
            "connection": _connection_payload(),
            "resume": False,
        },
    )
    assert response.status_code == 200, response.text

    frames = parse_sse_stream(response.text)
    event_names = [f["event"] for f in frames]

    # Stream contains at least one heartbeat (the baseline).
    assert "heartbeat" in event_names
    # Connect + scan tool events appear.
    tool_starts = [f for f in frames if f["event"] == "tool_start"]
    assert any(f["data"]["tool"] == "connect_to_database" for f in tool_starts)
    assert any(f["data"]["tool"] == "scan_metadata" for f in tool_starts)
    # PRD artifact emitted.
    prd = [f for f in frames if f["event"] == "artifact_update" and f["data"]["artifact_type"] == "prd"]
    assert len(prd) == 1
    payload = prd[0]["data"]["payload"]
    assert payload["sections"], "PRD must have sections"
    # Cited tables must come from the mock schema.
    cited = {t for s in payload["sections"] for t in s["cited_tables"]}
    assert "public.orders" in cited
    assert "public.customers" in cited
    # Exactly one terminal event, and it's `done`.
    terminals = [f for f in frames if f["event"] in ("done", "error", "artifact_ready")]
    assert len(terminals) == 1
    assert terminals[0]["event"] == "done"


def test_step_2_full_pipeline(client, session_headers, mock_driver):
    response = client.post(
        "/workflow/step",
        headers=session_headers,
        json={
            "step_id": "conceptual",
            "user_message": "Propose entities and relationships.",
            "prior_artifact": None,
            "connection": _connection_payload(),
            "resume": False,
        },
    )
    assert response.status_code == 200, response.text

    frames = parse_sse_stream(response.text)
    conceptual = [
        f for f in frames if f["event"] == "artifact_update" and f["data"]["artifact_type"] == "conceptual_model"
    ]
    assert len(conceptual) == 1
    payload = conceptual[0]["data"]["payload"]
    # 3 tables → 3 entities.
    assert len(payload["entities"]) == 3
    entity_labels = {e["label"] for e in payload["entities"]}
    assert {"Orders", "Customers", "Products"} <= entity_labels

    # Declared FK: orders → customers (N:1, not inferred)
    rels = payload["relationships"]
    assert len(rels) == 1
    assert rels[0]["cardinality"] == "N:1"
    assert rels[0]["inferred"] is False


def test_step_3_full_pipeline(client, session_headers, mock_driver):
    response = client.post(
        "/workflow/step",
        headers=session_headers,
        json={
            "step_id": "logical",
            "user_message": "Populate logical model.",
            "prior_artifact": None,
            "connection": _connection_payload(),
            "resume": False,
        },
    )
    assert response.status_code == 200, response.text

    frames = parse_sse_stream(response.text)
    logical = [
        f for f in frames if f["event"] == "artifact_update" and f["data"]["artifact_type"] == "logical_model"
    ]
    assert len(logical) == 1
    tables = logical[0]["data"]["payload"]["tables"]
    assert tables, "Logical model must have at least one table"
    for tbl in tables:
        for field in tbl["fields"]:
            assert field["data_type"], f"{tbl['id']}.{field['name']} has no data_type"
            assert 0 <= len(field["sample_values"]) <= 5


def test_step_4_produces_downloadable_zip(client, session_headers, mock_driver):
    response = client.post(
        "/workflow/step",
        headers=session_headers,
        json={
            "step_id": "detailed",
            "user_message": "Generate the dbt project.",
            "prior_artifact": None,
            "connection": _connection_payload(),
            "resume": False,
        },
    )
    assert response.status_code == 200, response.text

    frames = parse_sse_stream(response.text)
    ready = [f for f in frames if f["event"] == "artifact_ready"]
    assert len(ready) == 1
    handle = ready[0]["data"]["handle"]
    assert ready[0]["data"]["size_bytes"] > 0
    assert ready[0]["data"]["file_count"] > 0

    # Download the zip — path exercises GET /workflow/artifact/{handle} + session binding.
    download = client.get(
        f"/workflow/artifact/{handle}",
        headers={"X-DSA-Session-ID": session_headers["X-DSA-Session-ID"]},
    )
    assert download.status_code == 200
    assert download.headers["content-type"] == "application/zip"

    with zipfile.ZipFile(io.BytesIO(download.content)) as zf:
        names = zf.namelist()
        assert any(n.endswith("dbt_project.yml") for n in names), names
        assert any("/models/" in n for n in names), names

    # Single-use: second GET 404s.
    second = client.get(
        f"/workflow/artifact/{handle}",
        headers={"X-DSA-Session-ID": session_headers["X-DSA-Session-ID"]},
    )
    assert second.status_code == 404


def test_wrong_session_id_cant_download_artifact(client, session_headers, mock_driver):
    """Defense-in-depth: handles are bound to the session that created them."""
    response = client.post(
        "/workflow/step",
        headers=session_headers,
        json={
            "step_id": "detailed",
            "user_message": "Generate dbt.",
            "prior_artifact": None,
            "connection": _connection_payload(),
            "resume": False,
        },
    )
    assert response.status_code == 200
    frames = parse_sse_stream(response.text)
    handle = next(f["data"]["handle"] for f in frames if f["event"] == "artifact_ready")

    # Different session → 404 (not 403 — we chose 404 so a handle's existence
    # isn't leaked to a neighboring session).
    from uuid import uuid4

    other = client.get(
        f"/workflow/artifact/{handle}",
        headers={"X-DSA-Session-ID": str(uuid4())},
    )
    assert other.status_code == 404
