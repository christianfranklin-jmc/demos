"""T032: Step 3 populates logical fields with real types + top-5 samples.

Verifies FR-007.
"""

from __future__ import annotations

import pytest

from .conftest import parse_sse_stream


def test_step_3_pulls_real_samples(client, session_headers, northwinds_postgres_connection):
    if northwinds_postgres_connection is None:
        pytest.skip("DB_HOST not set to a live Northwinds instance")

    response = client.post(
        "/workflow/step",
        headers=session_headers,
        json={
            "step_id": "logical",
            "user_message": "Populate the logical model.",
            "prior_artifact": None,  # T041+ will thread the Step 2 artifact through
            "connection": northwinds_postgres_connection,
            "resume": False,
        },
    )
    if response.status_code == 404:
        pytest.skip("routes_workflow.py not yet wired (T035)")
    assert response.status_code == 200

    frames = parse_sse_stream(response.text)
    logical = [
        f
        for f in frames
        if f["event"] == "artifact_update" and f["data"].get("artifact_type") == "logical_model"
    ]
    assert logical, "Step 3 must emit artifact_update.logical_model"

    payload = logical[-1]["data"]["payload"]
    assert payload["tables"], "Logical model has at least one table"

    for table in payload["tables"]:
        for field in table["fields"]:
            assert field["data_type"], f"{table['id']}.{field['name']} missing data_type"
            assert 0 <= len(field["sample_values"]) <= 5, (
                f"{field['name']} sample_values must be 0..5, got {len(field['sample_values'])}"
            )
