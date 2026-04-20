"""T077: Streamlit regression smoke (FR-003, SC-006).

Launches ``streamlit run`` in a subprocess against a bootstrapped database,
hits the landing page, and asserts it responds 200. Env-gated: requires
DB_HOST + DB_PASSWORD to be set by ``scripts/bootstrap.sh``.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from contextlib import closing
from pathlib import Path

import pytest

try:
    import socket
    import urllib.request
except ImportError:  # pragma: no cover
    pytest.skip("stdlib missing", allow_module_level=True)


def _pick_port() -> int:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.mark.slow
def test_streamlit_app_boots():
    if not os.environ.get("DB_HOST") or os.environ["DB_HOST"].startswith(
        "platform-agent-northwinds.XXXX"
    ):
        pytest.skip("DB_HOST not configured")

    repo_root = Path(__file__).resolve().parents[2]
    app_path = repo_root / "streamlit_app" / "app.py"
    if not app_path.exists():
        pytest.skip("streamlit_app/app.py missing (should not happen post-integration)")

    port = _pick_port()
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            str(app_path),
            "--server.port",
            str(port),
            "--server.headless",
            "true",
            "--server.fileWatcherType",
            "none",
        ],
        cwd=str(repo_root),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    try:
        deadline = time.time() + 30
        last_err: Exception | None = None
        while time.time() < deadline:
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=1) as r:
                    assert r.status == 200
                    return
            except Exception as exc:
                last_err = exc
                time.sleep(0.5)
        raise AssertionError(f"Streamlit never responded within 30s: {last_err}")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
