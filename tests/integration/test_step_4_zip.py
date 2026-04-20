"""T033: Step 4 produces a downloadable, dbt-compile-clean zip.

Verifies FR-008 and SC-003 (100% dbt compile on first attempt).
"""

from __future__ import annotations

import io
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

import pytest

from .conftest import parse_sse_stream


def test_step_4_produces_compilable_dbt_zip(
    client, session_headers, northwinds_postgres_connection
):
    if northwinds_postgres_connection is None:
        pytest.skip("DB_HOST not set to a live Northwinds instance")

    response = client.post(
        "/workflow/step",
        headers=session_headers,
        json={
            "step_id": "detailed",
            "user_message": "Generate the dbt project.",
            "prior_artifact": None,  # T041+ will thread the logical model through
            "connection": northwinds_postgres_connection,
            "resume": False,
        },
    )
    if response.status_code == 404:
        pytest.skip("routes_workflow.py not yet wired (T035)")
    assert response.status_code == 200

    frames = parse_sse_stream(response.text)
    ready = [f for f in frames if f["event"] == "artifact_ready"]
    assert len(ready) == 1, f"Step 4 must emit exactly one artifact_ready; got {len(ready)}"

    handle = ready[0]["data"]["handle"]

    # Download the zip via the second HTTP request.
    download = client.get(
        f"/workflow/artifact/{handle}",
        headers={"X-DSA-Session-ID": session_headers["X-DSA-Session-ID"]},
    )
    assert download.status_code == 200
    assert download.headers["content-type"] == "application/zip"

    zip_bytes = download.content
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        names = zf.namelist()
        assert any(n.endswith("dbt_project.yml") for n in names), names
        assert any("/models/" in n for n in names), names

    # Second GET with the same handle must 404 (single-use).
    second = client.get(
        f"/workflow/artifact/{handle}",
        headers={"X-DSA-Session-ID": session_headers["X-DSA-Session-ID"]},
    )
    assert second.status_code == 404

    # dbt compile verification — only if `dbt` is on PATH.
    if shutil.which("dbt") is None:
        pytest.skip("dbt CLI not on PATH; skipping compile verification")

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            zf.extractall(tmp)
        project_dir = next(d for d in tmp.iterdir() if d.is_dir())
        result = subprocess.run(
            [
                "dbt",
                "compile",
                "--project-dir",
                str(project_dir),
                "--profiles-dir",
                str(project_dir),
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert result.returncode == 0, f"dbt compile failed:\n{result.stdout}\n{result.stderr}"
