"""Pill generator (US2 / FR-011, FR-012, R5).

Schema-grounded suggestion list for the Step-1 Discovery page. v1
implementation is deterministic — when both Pinnacle sources (PG with
ap/billing/crm/portfolio/performance/planning/gl/hr schemas + a
Snowflake analytical mirror) are live, the six named Pinnacle pills
are returned verbatim. Other workspaces fall back to a heuristic that
builds a pill per cross-source-overlapping process (SC-010 — non-
Pinnacle datasets produce pills reflecting *that* schema).

The Strands/Bedrock pill agent (R5) plugs in here in a follow-up
commit; the contract surface (signature, output shape) stays stable.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from platform_agent.semantic.models import Cardinality
from platform_agent.workflow.discovery_models import BusinessProcess
from platform_agent.workflow.pill_models import (
    IcebergTarget,
    PillFlags,
    PillSuggestion,
    PRDDraft,
    PRDOrigin,
    ProposedJoin,
    SourcePullSpec,
)
from platform_agent.workspace.models import Connection, DriverType

# ───── Pinnacle six-pill catalog (FR-012) ─────


# Each entry: (title, subtitle, icon, table_name, business_questions,
#              source schema hints per driver-family).
_PINNACLE_PILLS: list[dict] = [
    {
        "title": "Client 360",
        "subtitle": "combines: Postgres + Snowflake",
        "icon": "users-round",
        "table_name": "fct_client_360",
        "estimated_minutes": 4,
        "questions": [
            "What is the AUM-weighted advisor performance for top-decile clients?",
            "Which clients had >2 strategy meetings AND >5% AUM growth in Q1?",
            "What is the engagement score for our top 10 clients?",
        ],
        "pg_schemas": ["crm"],
        "sf_kind": "analytical",
    },
    {
        "title": "Revenue Waterfall",
        "subtitle": "combines: Postgres + Snowflake",
        "icon": "trending-up",
        "table_name": "fct_fee_attribution",
        "estimated_minutes": 4,
        "questions": [
            "What is fee revenue attribution by strategy and advisor?",
            "Which fee adjustments materially changed gross revenue last quarter?",
        ],
        "pg_schemas": ["billing"],
        "sf_kind": "analytical",
    },
    {
        "title": "Advisor Productivity",
        "subtitle": "combines: Postgres + Snowflake",
        "icon": "user-check",
        "table_name": "fct_advisor_productivity",
        "estimated_minutes": 3,
        "questions": [
            "Which advisors grew AUM the most relative to their meeting count?",
            "What is the meetings-per-AUM ratio across advisors?",
        ],
        "pg_schemas": ["crm"],
        "sf_kind": "analytical",
    },
    {
        "title": "Client Profitability",
        "subtitle": "combines: Postgres + Snowflake",
        "icon": "scale",
        "table_name": "fct_client_profitability",
        "estimated_minutes": 5,
        "questions": [
            "Which clients are unprofitable after allocated cost?",
            "What is the contribution margin per advisor relationship?",
        ],
        "pg_schemas": ["billing", "gl", "hr"],
        "sf_kind": "analytical",
    },
    {
        "title": "Trade Cost Attribution",
        "subtitle": "combines: Postgres + Snowflake",
        "icon": "candlestick-chart",
        "table_name": "fct_trade_economics",
        "estimated_minutes": 5,
        "questions": [
            "Which trades / rebalancing events had the highest realized cost?",
            "How does trade cost compare to attributed alpha?",
        ],
        "pg_schemas": ["portfolio", "gl"],
        "sf_kind": "analytical",
    },
    {
        "title": "Budget vs. AUM Reality",
        "subtitle": "combines: Postgres + Snowflake",
        "icon": "target",
        "table_name": "fct_plan_vs_aum",
        "estimated_minutes": 4,
        "questions": [
            "How does FP&A budgeted revenue compare to actual AUM-driven revenue?",
            "Where did Q2 AUM under/over-deliver vs the forecast?",
        ],
        "pg_schemas": ["planning"],
        "sf_kind": "analytical",
    },
]

DEFAULT_GLUE_DB = "pinnacle_360"
TARGET_REQUIRED_SENTINEL = "ICEBERG_TARGET_REQUIRED"

STANDARDS_APPLIED_DEFAULT = [
    "naming.kimball.fct_dim_prefixes",
    "naming.snake_case_columns",
    "iceberg.partition_by_period",
    "metrics.metricflow_yaml",
]


# ───── Public API ─────


def generate_pills(
    *,
    per_connection: list[tuple[Connection, list[BusinessProcess]]],
    min_pills: int = 6,
) -> list[PillSuggestion]:
    """Return ≥``min_pills`` schema-grounded PillSuggestions.

    Pinnacle layout (PG with 8 process schemas + Snowflake): returns the
    six named pills. Other layouts: returns one pill per process that
    appears in ≥2 connections (heuristic; ≥``min_pills`` enforced by
    padding with single-source suggestions if needed).
    """
    iceberg_target_id = _find_iceberg_connection_id(per_connection)
    pinnacle = _detect_pinnacle(per_connection)
    pg_conn_id = _connection_id_for(per_connection, DriverType.POSTGRESQL)
    sf_conn_id = _connection_id_for(per_connection, DriverType.SNOWFLAKE)

    if pinnacle and pg_conn_id and sf_conn_id:
        return [
            _build_pinnacle_pill(
                spec=spec,
                pg_conn_id=pg_conn_id,
                sf_conn_id=sf_conn_id,
                iceberg_connection_id=iceberg_target_id,
            )
            for spec in _PINNACLE_PILLS
        ]

    # Heuristic fallback for non-Pinnacle datasets (SC-010).
    return _heuristic_pills(
        per_connection=per_connection,
        iceberg_connection_id=iceberg_target_id,
        min_pills=min_pills,
    )


# ───── Pinnacle path ─────


def _build_pinnacle_pill(
    *,
    spec: dict,
    pg_conn_id: str,
    sf_conn_id: str,
    iceberg_connection_id: str,
) -> PillSuggestion:
    target_table = spec["table_name"]
    pg_pulls = [
        SourcePullSpec(
            connection_id=pg_conn_id,
            sql=f"SELECT * FROM {schema}.{schema}_overview LIMIT 250"
            if False
            else f"SELECT * FROM {schema}.{_PRIMARY_TABLE_HINT.get(schema, 'overview')} LIMIT 250",
            max_rows=250,
        )
        for schema in spec["pg_schemas"]
    ]
    sf_pulls = [
        SourcePullSpec(
            connection_id=sf_conn_id,
            sql=(
                "SELECT * FROM ANALYTICS.FCT_AUM_HISTORY "
                "WHERE snapshot_date >= CURRENT_DATE - 90 LIMIT 250"
            ),
            max_rows=250,
        )
    ]
    joins = [
        ProposedJoin(
            left_fqn=f"pinnacle.{schema}.{_PRIMARY_TABLE_HINT.get(schema, 'overview')}",
            right_fqn="PINNACLE_FINANCIAL_DEMO_ASINGH.ANALYTICS.FCT_AUM_HISTORY",
            keys=[("client_id", "CLIENT_ID")] if "crm" in spec["pg_schemas"]
            else [("account_id", "ACCOUNT_ID")],
            cardinality=Cardinality.ONE_TO_MANY,
        )
        for schema in spec["pg_schemas"]
    ]
    target = IcebergTarget(
        connection_id=iceberg_connection_id,
        glue_db=DEFAULT_GLUE_DB,
        table_name=target_table,
    )
    seed = PRDDraft(
        title=spec["title"],
        target=target,
        joins_identified=joins,
        business_questions=list(spec["questions"]),
        source_pulls=pg_pulls + sf_pulls,
        standards_applied=list(STANDARDS_APPLIED_DEFAULT),
        origin=PRDOrigin.PILL,
    )
    return PillSuggestion(
        pill_id=str(uuid4()),
        title=spec["title"],
        subtitle=spec["subtitle"],
        icon=spec["icon"],
        target_iceberg_table=f"iceberg.{DEFAULT_GLUE_DB}.{target_table}",
        source_connection_ids=[pg_conn_id, sf_conn_id],
        estimated_build_minutes=spec["estimated_minutes"],
        seed_prd_body=seed,
        generated_at=datetime.now(tz=UTC),
        flags=PillFlags(demo=False),
    )


# Best-known table per Pinnacle process schema (used for stub pull SQL).
_PRIMARY_TABLE_HINT: dict[str, str] = {
    "ap": "ap_invoice",
    "billing": "fee_invoice",
    "crm": "client",
    "gl": "JOURNAL_ENTRY",
    "hr": "employee",
    "performance": "account_aum_daily",
    "planning": "budget_line",
    "portfolio": "trade",
}


# ───── Heuristic fallback for non-Pinnacle datasets (SC-010) ─────


def _heuristic_pills(
    *,
    per_connection: list[tuple[Connection, list[BusinessProcess]]],
    iceberg_connection_id: str,
    min_pills: int,
) -> list[PillSuggestion]:
    """One pill per process that exists in ≥2 connections; pad to min_pills."""
    by_process: dict[str, list[tuple[Connection, BusinessProcess]]] = {}
    for conn, processes in per_connection:
        for p in processes:
            by_process.setdefault(p.name, []).append((conn, p))

    cross_source = [
        (name, members)
        for name, members in by_process.items()
        if len({c.connection_id for c, _ in members}) >= 2
    ]

    pills: list[PillSuggestion] = []
    for name, members in cross_source:
        connection_ids = [c.connection_id for c, _ in members]
        slug = name.lower().replace(" ", "_")
        seed = PRDDraft(
            title=f"{name} 360",
            target=IcebergTarget(
                connection_id=iceberg_connection_id,
                glue_db=DEFAULT_GLUE_DB,
                table_name=f"fct_{slug}",
            ),
            business_questions=[
                f"Unify {name} across {len(members)} sources into a single fact.",
            ],
            source_pulls=[
                SourcePullSpec(
                    connection_id=c.connection_id,
                    sql=f"SELECT * FROM {p.backing_tables[0]} LIMIT 250"
                    if p.backing_tables
                    else "SELECT 1",
                    max_rows=250,
                )
                for c, p in members
            ],
            standards_applied=list(STANDARDS_APPLIED_DEFAULT),
            origin=PRDOrigin.PILL,
        )
        pills.append(
            PillSuggestion(
                pill_id=str(uuid4()),
                title=f"{name} 360",
                subtitle="combines: " + " + ".join(c.driver_type.value for c, _ in members),
                icon="layers",
                target_iceberg_table=f"iceberg.{DEFAULT_GLUE_DB}.fct_{slug}",
                source_connection_ids=connection_ids,
                estimated_build_minutes=4,
                seed_prd_body=seed,
                generated_at=datetime.now(tz=UTC),
                flags=PillFlags(demo=False),
            )
        )

    # Pad with single-source suggestions until we hit min_pills, so the
    # contract's "≥6 pills" invariant holds for thin workspaces.
    if len(pills) < min_pills:
        for conn, processes in per_connection:
            for p in processes:
                if len(pills) >= min_pills:
                    break
                slug = p.name.lower().replace(" ", "_")
                seed = PRDDraft(
                    title=p.name,
                    target=IcebergTarget(
                        connection_id=iceberg_connection_id,
                        glue_db=DEFAULT_GLUE_DB,
                        table_name=f"fct_{slug}",
                    ),
                    business_questions=[f"Materialize {p.name} as an Iceberg fact."],
                    source_pulls=[
                        SourcePullSpec(
                            connection_id=conn.connection_id,
                            sql=f"SELECT * FROM {t} LIMIT 250" if t else "SELECT 1",
                            max_rows=250,
                        )
                        for t in (p.backing_tables[:1] or [""])
                    ],
                    standards_applied=list(STANDARDS_APPLIED_DEFAULT),
                    origin=PRDOrigin.PILL,
                )
                pills.append(
                    PillSuggestion(
                        pill_id=str(uuid4()),
                        title=p.name,
                        subtitle=f"single-source: {conn.driver_type.value}",
                        icon="square",
                        target_iceberg_table=f"iceberg.{DEFAULT_GLUE_DB}.fct_{slug}",
                        source_connection_ids=[conn.connection_id],
                        estimated_build_minutes=2,
                        seed_prd_body=seed,
                        generated_at=datetime.now(tz=UTC),
                        flags=PillFlags(demo=False),
                    )
                )
    return pills


# ───── Detection helpers ─────


def _detect_pinnacle(
    per_connection: list[tuple[Connection, list[BusinessProcess]]],
) -> bool:
    """Pinnacle-style PG iff ≥6 of the named process schemas are present."""
    pinnacle_names = {
        "Accounts Payable",
        "Client Fee Billing & Revenue",
        "CRM",
        "General Ledger",
        "HR & Cost Management",
        "Performance & Asset Reporting",
        "Financial Planning & Budgeting",
        "Portfolio Management & Trading",
    }
    for conn, processes in per_connection:
        if conn.driver_type != DriverType.POSTGRESQL:
            continue
        names = {p.name for p in processes}
        if len(names & pinnacle_names) >= 6:
            return True
    return False


def _connection_id_for(
    per_connection: list[tuple[Connection, list[BusinessProcess]]],
    driver_type: DriverType,
) -> str | None:
    for conn, _ in per_connection:
        if conn.driver_type == driver_type:
            return conn.connection_id
    return None


def _find_iceberg_connection_id(
    per_connection: list[tuple[Connection, list[BusinessProcess]]],
) -> str:
    for conn, _ in per_connection:
        if conn.driver_type == DriverType.ICEBERG:
            return conn.connection_id
    return TARGET_REQUIRED_SENTINEL
