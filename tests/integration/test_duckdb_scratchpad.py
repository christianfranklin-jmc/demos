"""DuckDB scratchpad integration tests (T092, US4).

Exercises the in-process join end-to-end: registers two pulls as views,
runs a real DuckDB INNER JOIN, asserts row caps + truncation flags +
read-only enforcement.
"""

from __future__ import annotations

import pytest

from platform_agent.tools.duckdb_scratchpad import (
    CrossSourceQueryRequest,
    SourcePullResult,
    cross_source_query,
)
from platform_agent.workspace.read_only import ReadOnlyViolation


def _pull(view: str, columns: list[str], rows: list[dict]) -> SourcePullResult:
    return SourcePullResult(
        connection_id="conn-" + view,
        view_name=view,
        columns=columns,
        rows=rows,
        truncated_at_cap=False,
    )


def test_inner_join_two_pulls() -> None:
    pg = _pull(
        "pg_clients",
        ["client_id", "name"],
        [
            {"client_id": 1, "name": "Alice"},
            {"client_id": 2, "name": "Bob"},
            {"client_id": 3, "name": "Carol"},
        ],
    )
    sf = _pull(
        "sf_aum",
        ["client_id", "ending_aum"],
        [
            {"client_id": 1, "ending_aum": 1_000_000},
            {"client_id": 2, "ending_aum": 2_500_000},
        ],
    )
    out = cross_source_query(
        CrossSourceQueryRequest(
            pulls=[pg, sf],
            join_sql=(
                "SELECT pg.client_id, pg.name, sf.ending_aum "
                "FROM pg_clients pg INNER JOIN sf_aum sf "
                "ON pg.client_id = sf.client_id"
            ),
        )
    )
    assert out.rows_returned == 2
    assert out.columns == ["client_id", "name", "ending_aum"]
    names = sorted(r["name"] for r in out.rows)
    assert names == ["Alice", "Bob"]
    assert not out.truncated_at_cap


def test_join_caps_at_5000() -> None:
    big = _pull(
        "big",
        ["k", "v"],
        [{"k": i, "v": i * 2} for i in range(250)],
    )
    other = _pull(
        "other",
        ["k", "label"],
        [{"k": i, "label": "x"} for i in range(250)],
    )
    # CROSS JOIN produces 250×250 = 62,500 rows; cap=5,000.
    out = cross_source_query(
        CrossSourceQueryRequest(
            pulls=[big, other],
            join_sql="SELECT b.k, b.v, o.label FROM big b CROSS JOIN other o",
            join_cap=5000,
        )
    )
    assert out.rows_returned == 5000
    assert out.truncated_at_cap is True


def test_per_source_pull_cap_rejected_at_validate() -> None:
    too_big = _pull(
        "too_big",
        ["k"],
        [{"k": i} for i in range(251)],
    )
    other = _pull("other", ["k"], [{"k": 0}])
    with pytest.raises(ValueError, match="per-source cap is 250"):
        cross_source_query(
            CrossSourceQueryRequest(
                pulls=[too_big, other],
                join_sql="SELECT * FROM too_big a JOIN other b ON a.k = b.k",
            )
        )


def test_read_only_blocks_write_join_sql() -> None:
    pg = _pull("pg", ["k"], [{"k": 1}])
    sf = _pull("sf", ["k"], [{"k": 1}])
    with pytest.raises(ReadOnlyViolation):
        cross_source_query(
            CrossSourceQueryRequest(
                pulls=[pg, sf],
                join_sql="DROP TABLE pg",
            )
        )


def test_view_name_pattern_enforced() -> None:
    """Invalid view_names are rejected at Pydantic construction time."""
    with pytest.raises(ValueError):
        _pull("bad-name!", ["k"], [{"k": 1}])


def test_duplicate_view_names_rejected() -> None:
    a = _pull("dup", ["k"], [{"k": 1}])
    b = _pull("dup", ["k"], [{"k": 2}])
    with pytest.raises(ValueError, match="duplicate view_name"):
        cross_source_query(
            CrossSourceQueryRequest(
                pulls=[a, b],
                join_sql="SELECT 1",
            )
        )


def test_empty_pulls_rejected() -> None:
    with pytest.raises(ValueError, match="≥1 entry"):
        cross_source_query(
            CrossSourceQueryRequest(pulls=[], join_sql="SELECT 1")
        )
