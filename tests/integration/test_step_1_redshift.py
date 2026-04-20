"""T051: Full workflow against Redshift Northwinds; asserts Step 4 produces
a dbt-redshift-targeted project.
"""

from __future__ import annotations

import io
import zipfile

import pytest

from .conftest import parse_sse_stream


def test_step_4_produces_redshift_dbt_project(
    client, session_headers, redshift_connection
):
    if redshift_connection is None:
        pytest.skip("RS_HOST not configured")

    # Go directly to Step 4; Step 2/3 threading is deferred to a later pass.
    response = client.post(
        "/workflow/step",
        headers=session_headers,
        json={
            "step_id": "detailed",
            "user_message": "Generate the dbt project.",
            "prior_artifact": None,
            "connection": redshift_connection,
            "resume": False,
        },
    )
    assert response.status_code == 200

    frames = parse_sse_stream(response.text)
    ready = [f for f in frames if f["event"] == "artifact_ready"]
    assert len(ready) == 1

    handle = ready[0]["data"]["handle"]
    download = client.get(
        f"/workflow/artifact/{handle}",
        headers={"X-DSA-Session-ID": session_headers["X-DSA-Session-ID"]},
    )
    assert download.status_code == 200

    with zipfile.ZipFile(io.BytesIO(download.content)) as zf:
        profiles = next((n for n in zf.namelist() if n.endswith("profiles.yml")), None)
        assert profiles, f"No profiles.yml in zip: {zf.namelist()}"
        contents = zf.read(profiles).decode("utf-8")
        # Generated profiles.yml MUST target the redshift adapter for a Redshift source.
        assert "redshift" in contents.lower(), (
            f"Redshift source must produce a dbt-redshift profiles.yml; got:\n{contents[:400]}"
        )
