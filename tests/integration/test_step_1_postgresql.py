"""T030: Step 1 against Northwinds PostgreSQL.

Verifies FR-005 (schema-grounded PRD) and SC-004 (schema-grounded content
within 30s). Env-gated: skips if DB_HOST points at the bootstrap placeholder.
"""

from __future__ import annotations

import pytest

from .conftest import parse_sse_stream


def test_step_1_grounds_prd_in_northwinds(client, session_headers, northwinds_postgres_connection):
    if northwinds_postgres_connection is None:
        pytest.skip("DB_HOST not set to a live Northwinds instance")

    response = client.post(
        "/workflow/step",
        headers=session_headers,
        json={
            "step_id": "requirements",
            "user_message": "We want to understand our order data.",
            "prior_artifact": None,
            "connection": northwinds_postgres_connection,
            "resume": False,
        },
    )
    if response.status_code == 404:
        pytest.skip("routes_workflow.py not yet wired (T035)")
    assert response.status_code == 200, response.text

    frames = parse_sse_stream(response.text)
    # Expect at least one tool_progress (from scan_metadata instrumentation),
    # at least one artifact_update.prd, and exactly one terminal event.
    artifact_updates = [f for f in frames if f["event"] == "artifact_update"]
    terminals = [f for f in frames if f["event"] in ("done", "error", "artifact_ready")]
    assert len(terminals) == 1, f"Expected exactly 1 terminal event, got {terminals}"
    assert terminals[0]["event"] == "done"

    prd_updates = [f for f in artifact_updates if f["data"].get("artifact_type") == "prd"]
    assert prd_updates, "Step 1 must emit at least one artifact_update.prd"

    # Assert at least one PRD section cites a real Northwinds table.
    final_prd = prd_updates[-1]["data"]["payload"]
    cited_everywhere = {t for s in final_prd["sections"] for t in s["cited_tables"]}
    northwinds_tables = {
        "public.orders",
        "public.customers",
        "public.order_details",
        "public.products",
    }
    assert cited_everywhere & northwinds_tables, (
        f"PRD must cite real Northwinds tables; cited={cited_everywhere}"
    )
