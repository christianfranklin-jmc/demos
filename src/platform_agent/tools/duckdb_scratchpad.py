"""DuckDB scratchpad — in-process cross-source join (T093, US4 / R4).

Takes a list of per-source pulls (already executed via the right
DatabaseDriver), registers each result as a DuckDB view in a fresh
session, runs the SELECT/WITH-only join SQL the caller supplies, and
returns the joined rows + truncation flags.

Caps: 250 rows per source pull, 5,000 rows for the joined result
(FR-018, SC-006). The DuckDB session is throwaway — opened per call,
torn down on return — so no data persists across turns.

The LLM-driven cross-source query planner (R4 D2) plugs in *above*
this tool: the planner decides what to SELECT from each source, this
tool stitches the pulls together. The contract surface (input shape,
output shape) does not change between the deterministic and LLM paths.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from pydantic import BaseModel, Field

from platform_agent.workspace.read_only import (
    ReadOnlyViolation,
    assert_read_only,
)

logger = logging.getLogger(__name__)


# ───── Contract types ─────


class SourcePullResult(BaseModel):
    """A pull's pre-fetched rows + metadata (already capped per FR-018)."""

    connection_id: str
    view_name: str = Field(
        ...,
        description="DuckDB view alias for the join SQL to reference.",
        pattern=r"^[A-Za-z_][A-Za-z0-9_]*$",
    )
    columns: list[str]
    rows: list[dict[str, Any]]
    truncated_at_cap: bool = False


class CrossSourceQueryRequest(BaseModel):
    """Inputs the planner / @tool hands to the scratchpad."""

    pulls: list[SourcePullResult]
    join_sql: str = Field(
        ...,
        description=(
            "SELECT/WITH-only SQL referencing the registered views by their "
            "view_name aliases. Joined output is capped at "
            "DSA_HUB_DUCKDB_JOIN_CAP rows (default 5000)."
        ),
    )
    join_cap: int = Field(default=5000, ge=1, le=5000)


class CrossSourceQueryResult(BaseModel):
    columns: list[str]
    rows: list[dict[str, Any]]
    rows_returned: int
    truncated_at_cap: bool
    join_sql: str
    per_source: list[SourcePullResult]


# ───── Read-only / view-name guards ─────


_VIEW_NAME_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _validate(payload: CrossSourceQueryRequest) -> None:
    if not payload.pulls:
        raise ValueError("CrossSourceQueryRequest.pulls must contain ≥1 entry")
    seen: set[str] = set()
    for pull in payload.pulls:
        if not _VIEW_NAME_PATTERN.match(pull.view_name):
            raise ValueError(f"invalid view_name {pull.view_name!r}")
        if pull.view_name in seen:
            raise ValueError(f"duplicate view_name {pull.view_name!r}")
        seen.add(pull.view_name)
        if len(pull.rows) > 250:
            raise ValueError(
                f"pull {pull.view_name} has {len(pull.rows)} rows; per-source cap is 250"
            )
    try:
        assert_read_only(payload.join_sql)
    except ReadOnlyViolation:
        raise


# ───── Public entry point ─────


def cross_source_query(payload: CrossSourceQueryRequest) -> CrossSourceQueryResult:
    """Run a one-shot cross-source join in DuckDB and return the result.

    Idempotent: every call opens a fresh in-memory DuckDB connection.
    The caller is responsible for performing the per-source pulls.
    """
    _validate(payload)

    import duckdb  # imported lazily — duckdb is a heavyweight dep

    con = duckdb.connect(database=":memory:")
    try:
        for pull in payload.pulls:
            cols = pull.columns or _columns_from_rows(pull.rows)
            types = _infer_column_types(pull.rows, cols)
            decl = ", ".join(
                f"{_quote_ident(c)} {t}" for c, t in zip(cols, types, strict=False)
            )
            con.execute(f'CREATE TEMP TABLE "{pull.view_name}" ({decl})')
            if pull.rows:
                placeholders = "(" + ", ".join("?" * len(cols)) + ")"
                rows_as_tuples = [
                    tuple(row.get(c) for c in cols) for row in pull.rows
                ]
                con.executemany(
                    f'INSERT INTO "{pull.view_name}" VALUES {placeholders}',
                    rows_as_tuples,
                )

        # Run the join with a hard LIMIT applied above the user's join_sql.
        # We wrap so a missing/oversized LIMIT in the caller's SQL still
        # respects FR-018.
        capped_sql = (
            f"SELECT * FROM ({payload.join_sql}) AS _cross_source_join "
            f"LIMIT {int(payload.join_cap) + 1}"
        )
        cur = con.execute(capped_sql)
        col_names = [d[0] for d in cur.description]
        all_rows = cur.fetchall()
    finally:
        con.close()

    truncated = len(all_rows) > payload.join_cap
    rows = all_rows[: payload.join_cap]
    return CrossSourceQueryResult(
        columns=col_names,
        rows=[dict(zip(col_names, r, strict=False)) for r in rows],
        rows_returned=len(rows),
        truncated_at_cap=truncated,
        join_sql=payload.join_sql,
        per_source=payload.pulls,
    )


# ───── Helpers ─────


def _columns_from_rows(rows: list[dict[str, Any]]) -> list[str]:
    seen: dict[str, None] = {}
    for r in rows:
        for k in r:
            if k not in seen:
                seen[k] = None
    return list(seen.keys())


def _infer_column_types(
    rows: list[dict[str, Any]], columns: list[str]
) -> list[str]:
    """Pick a DuckDB type for each column from the first non-null sample.

    Defaults to VARCHAR when every value is None — keeps the table
    queryable rather than collapsing the row to INTEGER NULLs (which
    would then reject incoming string data).
    """
    out: list[str] = []
    for col in columns:
        sample: Any = None
        for r in rows:
            v = r.get(col)
            if v is not None:
                sample = v
                break
        if isinstance(sample, bool):
            out.append("BOOLEAN")
        elif isinstance(sample, int):
            out.append("BIGINT")
        elif isinstance(sample, float):
            out.append("DOUBLE")
        else:
            out.append("VARCHAR")
    return out


def _quote_ident(name: str) -> str:
    if not _VIEW_NAME_PATTERN.match(name):
        raise ValueError(f"invalid identifier {name!r}")
    return f'"{name}"'


__all__ = [
    "cross_source_query",
    "CrossSourceQueryRequest",
    "CrossSourceQueryResult",
    "SourcePullResult",
]
