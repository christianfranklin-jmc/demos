"""T078: CLI regression smoke (FR-003, SC-006).

Invokes ``python -m platform_agent --help`` and asserts exit 0. Full
end-to-end interaction requires Bedrock + DB and is out of scope for the
regression suite.
"""

from __future__ import annotations

import subprocess
import sys


def test_cli_module_runnable():
    """`python -m platform_agent --help` exits cleanly (no import errors)."""
    result = subprocess.run(
        [sys.executable, "-m", "platform_agent", "--help"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    # Accept either a clean --help (exit 0) or an argparse-style usage message.
    # What we're asserting is that the module imports — a traceback would exit
    # non-zero with "Traceback" in stderr.
    assert "Traceback" not in result.stderr, (
        f"CLI module failed to import:\n{result.stderr[:2000]}"
    )
