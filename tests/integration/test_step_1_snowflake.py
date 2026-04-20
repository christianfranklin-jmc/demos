"""T050: Step 1 against the Pinnacle Financial Snowflake demo.

Env-gated via SF_ACCOUNT; skips cleanly when the Snowflake account isn't
configured. Verifies that the PRD cites real PINNACLE_FINANCIAL_DEMO tables.
"""

from __future__ import annotations

import pytest

from .conftest import parse_sse_stream


def test_step_1_cites_pinnacle_tables(client, session_headers, pinnacle_snowflake_connection):
    if pinnacle_snowflake_connection is None:
        pytest.skip("SF_ACCOUNT not configured")

    response = client.post(
        "/workflow/step",
        headers=session_headers,
        json={
            "step_id": "requirements",
            "user_message": "Understand our client book.",
            "prior_artifact": None,
            "connection": pinnacle_snowflake_connection,
            "resume": False,
        },
    )
    assert response.status_code == 200, response.text

    frames = parse_sse_stream(response.text)
    prd = [
        f
        for f in frames
        if f["event"] == "artifact_update" and f["data"].get("artifact_type") == "prd"
    ]
    assert prd, "Step 1 must emit artifact_update.prd"

    cited = {t for s in prd[-1]["data"]["payload"]["sections"] for t in s["cited_tables"]}
    # Pinnacle Financial uses 5 dims + 4 facts. Just require at least one real table.
    assert any("ANALYTICS." in t or "DIM_" in t.upper() or "FCT_" in t.upper() for t in cited), (
        f"PRD must cite a real Pinnacle table; cited={cited}"
    )
