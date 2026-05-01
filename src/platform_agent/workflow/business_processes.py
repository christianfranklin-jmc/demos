"""Business-process detection from a scanned schema (US2 / FR-008).

Pinnacle stores each process in its own schema (`ap`, `billing`, `crm`,
`gl`, `hr`, `performance`, `planning`, `portfolio`) so detection is
deterministic by schema name. Datasets that don't follow this convention
fall back to "schema name as process name" and an `unspecified` domain,
which still satisfies SC-010 (non-Pinnacle data produces process cards
that reflect that schema, not Pinnacle's).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from platform_agent.semantic.models import Domain
from platform_agent.workflow.discovery_models import (
    BusinessProcess,
    VolumeSignal,
)

# Schema name → (display name, domain). Schemas not in this map are
# treated as `unspecified` with the schema name capitalized.
PINNACLE_PROCESSES: dict[str, tuple[str, Domain]] = {
    "ap": ("Accounts Payable", Domain.ACCOUNTING),
    "billing": ("Client Fee Billing & Revenue", Domain.ACCOUNTING),
    "crm": ("CRM", Domain.CRM),
    "gl": ("General Ledger", Domain.ACCOUNTING),
    "hr": ("HR & Cost Management", Domain.HR),
    "performance": ("Performance & Asset Reporting", Domain.WEALTH_MGMT),
    "planning": ("Financial Planning & Budgeting", Domain.PLANNING),
    "portfolio": ("Portfolio Management & Trading", Domain.WEALTH_MGMT),
}

# Columns that are valuable to surface in volume signals — for revenue/AUM/
# spend-style processes the dollar total is part of the volume tile.
DOLLAR_COLUMN_HINTS = (
    "amount",
    "total",
    "notional",
    "balance",
    "ending_aum",
    "beg_aum",
    "market_value",
)


def _process_for_schema(schema: str) -> tuple[str, Domain]:
    """Return (display_name, domain) for a schema; falls back gracefully."""
    if schema in PINNACLE_PROCESSES:
        return PINNACLE_PROCESSES[schema]
    return (schema.replace("_", " ").title(), Domain.UNSPECIFIED)


def _row_count_for_schema(tables: list[dict[str, Any]]) -> int:
    return sum(int(t.get("row_count") or 0) for t in tables)


def detect_business_processes(
    *,
    connection_id: str,
    metadata: dict[str, Any],
) -> list[BusinessProcess]:
    """Build a list of BusinessProcess records from a scan_metadata payload.

    One BusinessProcess per non-system schema. Tables in the same schema
    are aggregated into the process's volume signal and ``backing_tables``.
    """
    by_schema: dict[str, list[dict[str, Any]]] = {}
    for tbl in metadata.get("tables", []):
        schema = str(tbl.get("schema") or "public")
        by_schema.setdefault(schema, []).append(tbl)

    now = datetime.now(tz=UTC)
    out: list[BusinessProcess] = []
    for schema, tables in sorted(by_schema.items()):
        display, domain = _process_for_schema(schema)
        row_count = _row_count_for_schema(tables)
        out.append(
            BusinessProcess(
                process_id=str(uuid4()),
                connection_id=connection_id,
                name=display,
                domain=domain,
                volume_signal=VolumeSignal(
                    row_count=row_count,
                    # Dollar totals require live data sampling (deferred to
                    # T138 perf verification + Step-1 polish). Keep None
                    # here so the contract stays honest.
                    dollar_total=None,
                    currency=None,
                ),
                last_activity_ts=now,
                # 12 zero buckets satisfy the schema; sparkline data lands
                # when daily/weekly aggregation is wired in US2 polish.
                sparkline=[0.0] * 12,
                backing_tables=[
                    f"{metadata.get('database', 'db')}.{schema}.{t['table_name']}"
                    for t in tables
                ],
            )
        )
    return out
