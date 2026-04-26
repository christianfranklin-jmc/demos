"""Cross-source CoverageMatrix construction (US2 / FR-010).

Given per-connection BusinessProcess lists (workflow/business_processes.py)
plus the underlying scan_metadata payloads, build a workspace-level
:class:`CoverageMatrix` that shows which processes exist in which
connection and where shared business keys make a cross-source data
product feasible.

"Ready to combine" is true iff a process appears in ≥2 connections AND
the union of column names across its backing tables shares ≥1 of the
shared-key candidates (e.g., ``client_id``, ``account_id``).
"""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from platform_agent.workflow.discovery_models import (
    BusinessProcess,
    CoverageMatrix,
    CoverageRow,
    ProcessPresence,
)

# Column names commonly used to join across sources. These are
# Pinnacle-aligned; any dataset using these conventions benefits.
SHARED_KEY_CANDIDATES = (
    "client_id",
    "account_id",
    "strategy_id",
    "advisor_id",
    "portfolio_id",
    "household_id",
)


def _columns_for_process(
    process: BusinessProcess,
    metadata: dict[str, Any],
) -> set[str]:
    """Collect lowercased column names from every backing table of a process."""
    backing_set = set(process.backing_tables)
    cols: set[str] = set()
    for tbl in metadata.get("tables", []):
        fqn = (
            f"{metadata.get('database', 'db')}.{tbl.get('schema', 'public')}."
            f"{tbl['table_name']}"
        )
        if fqn not in backing_set:
            continue
        for col in tbl.get("columns", []):
            name = col.get("column_name") or col.get("name")
            if name:
                cols.add(str(name).lower())
    return cols


def build_coverage_matrix(
    *,
    workspace_id: UUID,
    per_connection: list[
        tuple[str, list[BusinessProcess], dict[str, Any]]
    ],
) -> CoverageMatrix:
    """Construct a CoverageMatrix from per-connection (id, processes, metadata).

    The matrix has one row per **process name** (display name) seen across
    any connection. Each row records presence per connection_id, the
    cross-source shared keys, and the ready-to-combine flag.
    """
    # Index processes by display name → connection_id → BusinessProcess
    by_name: dict[str, dict[str, BusinessProcess]] = {}
    columns_index: dict[str, dict[str, set[str]]] = {}
    for connection_id, processes, metadata in per_connection:
        cols_per_process = {
            p.name: _columns_for_process(p, metadata) for p in processes
        }
        for p in processes:
            by_name.setdefault(p.name, {})[connection_id] = p
            columns_index.setdefault(p.name, {})[connection_id] = cols_per_process[
                p.name
            ]

    rows: list[CoverageRow] = []
    for name, by_conn in sorted(by_name.items()):
        # Per-connection presence
        per_connection_map: dict[str, ProcessPresence] = {}
        for connection_id in by_conn:
            per_connection_map[connection_id] = ProcessPresence(
                present=True,
                backing_tables=list(by_conn[connection_id].backing_tables),
            )
        # Shared keys across connections that *both* report this process
        shared: list[str] = []
        if len(by_conn) >= 2:
            cols_per_conn = columns_index[name]
            present_conns = list(cols_per_conn.keys())
            common = set.intersection(
                *[cols_per_conn[c] for c in present_conns]
            )
            shared = sorted(common.intersection(SHARED_KEY_CANDIDATES))
        rows.append(
            CoverageRow(
                process_name=name,
                per_connection=per_connection_map,
                shared_keys=shared,
                ready_to_combine=len(by_conn) >= 2 and bool(shared),
            )
        )
    return CoverageMatrix(
        matrix_id=str(uuid4()),
        workspace_id=workspace_id,
        rows=rows,
    )
