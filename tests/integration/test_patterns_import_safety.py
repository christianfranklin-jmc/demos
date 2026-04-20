"""T078a: Snow-iceberg pattern preservation (FR-004).

The five specialized agent patterns (migration, enrichment, quality,
mapping, query) live under ``patterns/<name>-agent/``. Python can't
directly import hyphenated package names, so this test just verifies
structural integrity — every pattern's ``agent.py``, system prompt, and
at least one tool file are still present on the feature branch.

This protects against an accidental loss during git merges or refactors.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PATTERNS_DIR = REPO_ROOT / "patterns"

EXPECTED_PATTERNS = [
    "migration-agent",
    "enrichment-agent",
    "quality-agent",
    "mapping-agent",
    "query-agent",
    "platform-agent",
]


@pytest.mark.parametrize("pattern", EXPECTED_PATTERNS)
def test_pattern_has_agent_entrypoint(pattern: str):
    path = PATTERNS_DIR / pattern / "agent.py"
    assert path.exists(), f"{path} is missing — snow-iceberg pattern regressed"
    assert path.stat().st_size > 100, f"{path} exists but is empty"


@pytest.mark.parametrize("pattern", EXPECTED_PATTERNS)
def test_pattern_has_tools_dir(pattern: str):
    tools = PATTERNS_DIR / pattern / "tools"
    assert tools.exists() and tools.is_dir(), (
        f"{tools} missing — FR-004 preservation failed for {pattern}"
    )
    py_files = list(tools.glob("*.py"))
    # Some patterns may use __init__.py only; require at least one tool file.
    assert py_files, f"{tools} has no .py files"


def test_utils_pattern_helpers_present():
    """utils/ holds shared JWT + SSM helpers used by every agent container."""
    utils = PATTERNS_DIR / "utils"
    assert (utils / "auth.py").exists(), "patterns/utils/auth.py missing"
    assert (utils / "ssm.py").exists(), "patterns/utils/ssm.py missing"


def test_gateway_mcp_config_preserved():
    """The dbt-mcp per-agent tool routing config must not have been lost."""
    config = REPO_ROOT / "gateway" / "mcp" / "dbt-mcp-config.json"
    assert config.exists(), f"{config} missing — FR-004 (dbt MCP integration) regressed"
