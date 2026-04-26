"""Read-only SQL enforcement (FR-018, SC-006).

Single source of truth for the SELECT/WITH-only regex used at every
query path: TTYD planner, semantic-graph metric definitions, source
pulls in PRDs, DuckDB scratchpad join SQL.
"""

from __future__ import annotations

import re

# Block writes; allow `CREATE OR REPLACE VIEW` since DuckDB scratchpad
# registers per-source pulls as views inside the throwaway session.
_WRITE_KEYWORD_PATTERN = re.compile(
    r"\b(?:INSERT|UPDATE|DELETE|DROP|TRUNCATE|ALTER|MERGE|GRANT|REVOKE|"
    r"CREATE\s+(?!OR\s+REPLACE\s+VIEW))\b",
    re.IGNORECASE,
)


class ReadOnlyViolation(ValueError):
    """Raised when SQL contains a write keyword."""


def is_read_only(sql: str) -> bool:
    return _WRITE_KEYWORD_PATTERN.search(sql) is None


def assert_read_only(sql: str) -> None:
    """Raise ReadOnlyViolation if sql contains any blocked write keyword."""
    if not is_read_only(sql):
        match = _WRITE_KEYWORD_PATTERN.search(sql)
        keyword = match.group(0) if match else "unknown"
        raise ReadOnlyViolation(
            f"read_only_violation: write keyword '{keyword.strip()}' is not permitted"
        )
