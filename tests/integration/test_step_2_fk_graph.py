"""T031: Step 2 conceptual model derived from the real FK graph.

Verifies FR-006 (FK-derived entities/relationships).
"""

from __future__ import annotations

import pytest

from .conftest import parse_sse_stream


def test_step_2_builds_fk_graph_from_northwinds(
    client, session_headers, northwinds_postgres_connection
):
    if northwinds_postgres_connection is None:
        pytest.skip("DB_HOST not set to a live Northwinds instance")

    response = client.post(
        "/workflow/step",
        headers=session_headers,
        json={
            "step_id": "conceptual",
            "user_message": "Propose entities and relationships.",
            "prior_artifact": None,
            "connection": northwinds_postgres_connection,
            "resume": False,
        },
    )
    if response.status_code == 404:
        pytest.skip("routes_workflow.py not yet wired (T035)")
    assert response.status_code == 200, response.text

    frames = parse_sse_stream(response.text)
    conceptual = [
        f
        for f in frames
        if f["event"] == "artifact_update" and f["data"].get("artifact_type") == "conceptual_model"
    ]
    assert conceptual, "Step 2 must emit artifact_update.conceptual_model"

    payload = conceptual[-1]["data"]["payload"]
    assert len(payload["entities"]) >= 6, f"Expected ≥6 entities, got {len(payload['entities'])}"

    # At least one declared (non-inferred) relationship between orders and customers.
    rels = payload["relationships"]
    order_customer = [
        r
        for r in rels
        if {"orders", "customers"}.issubset(
            {r["from_entity_id"].lower(), r["to_entity_id"].lower()}
        )
        and not r["inferred"]
    ]
    assert order_customer, "Orders↔Customers FK must appear as a non-inferred relationship"
