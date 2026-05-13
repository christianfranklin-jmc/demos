"""Sigma dashboard analysis using Bedrock vision and/or SQL introspection.

Three analysis paths:
1. Vision extraction — extract metrics, datasets, and column hints from a screenshot.
2. SQL analysis — parse Sigma-exported SQL queries for precise column/table extraction.
3. Schema mapping — map extracted artifacts to source tables and generate dbt + repointing plan.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

import boto3

logger = logging.getLogger(__name__)

BEDROCK_MODEL_ID = "us.anthropic.claude-sonnet-4-20250514-v1:0"
BEDROCK_REGION = "us-east-1"


def _bedrock_client() -> Any:
    return boto3.client("bedrock-runtime", region_name=BEDROCK_REGION)


def _parse_data_url(data_url: str) -> tuple[str, str]:
    """Parse 'data:image/jpeg;base64,...' → (media_type, b64_string)."""
    if "," not in data_url:
        raise ValueError("Expected a data URL with a comma separator")
    header, b64_data = data_url.split(",", 1)
    media_type = header.split(";")[0][len("data:"):]
    return media_type, b64_data


def _schema_summary(tables: list[dict]) -> str:
    lines: list[str] = []
    for t in tables[:20]:
        name = t.get("name") or t.get("table_name", "")
        if not name:
            continue
        row_count = t.get("row_count", "?")
        cols = t.get("columns") or []
        col_list = ", ".join(
            f"{c.get('name') or c.get('column_name', '?')} {c.get('data_type') or c.get('type', '')}"
            for c in cols[:12]
            if c.get("name") or c.get("column_name")
        )
        lines.append(f"  {name} [{row_count} rows]: {col_list}")
    return "\n".join(lines) or "(no tables scanned)"


def _strip_code_fence(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\n?", "", text)
    text = re.sub(r"\n?```$", "", text)
    return text.strip()


# ───────── Prompt 1a: Sigma-aware vision extraction ─────────

_VISION_PROMPT = """\
You are analyzing a Sigma Analytics workbook screenshot for a data engineering reverse-engineering task.

Sigma is a cloud BI tool that queries data warehouses (Snowflake, BigQuery, Redshift) directly.
Every Sigma workbook has one or more "datasets" — connections to underlying warehouse tables or views.

Extract the following from the screenshot:

1. WORKBOOK CONTEXT
   - workbook_name: the title shown at the top of the page or browser tab
   - domain: business area (RevOps, Finance, Sales, Marketing, HR, Operations)
   - dominant_grain: the most common time grain visible (daily/weekly/monthly/quarterly/annual)

2. SIGMA DATASETS (look in breadcrumbs, the left-side data panel, or element sources)
   - Any visible dataset names, schema.table references, or connection info
   - Examples: "Opportunities", "public.accounts", "ANALYTICS.FACT_ARR"

3. METRICS (every chart, table, KPI tile, and pivot visible)
   - label: exact text label shown
   - chart_type: bar, line, kpi_tile, table, pivot, scatter, waterfall, area, combo
   - dimensions: grouping dimensions (axis labels, column headers, row groupings)
   - time_grain: the grain for this specific metric
   - aggregation: sum, count, countd, average, percent, ratio, median
   - description: plain English explanation of what this metric measures

4. COLUMN CLUES (any column/field names visible anywhere)
   - Filter pills showing "ColumnName = value" or "Date Range: last 12 months"
   - Tooltip/axis labels with field names like "rep_name", "arr_usd", "close_date"
   - Left-side data panel column list (if visible)

5. CALCULATIONS (any visible calculated/custom columns or formulas)
   - Sigma formulas often appear in column headers as "formula_name" or show in tooltips

Return JSON only, no prose:
{
  "workbook_name": "...",
  "domain": "...",
  "dominant_grain": "monthly",
  "sigma_datasets": ["schema.table_or_dataset_name"],
  "current_source_hints": ["schema.table", "column_name"],
  "visible_column_names": ["arr_usd", "close_date", "rep_name"],
  "metrics": [
    {
      "label": "...",
      "chart_type": "...",
      "dimensions": ["..."],
      "time_grain": "...",
      "aggregation": "...",
      "description": "..."
    }
  ],
  "sigma_calculations": [
    {"name": "...", "formula": "...", "description": "..."}
  ]
}"""


# ───────── Prompt 1b: SQL-based extraction (when user provides Sigma SQL export) ─────────

_SQL_ANALYSIS_PROMPT_TEMPLATE = """\
You are analyzing SQL queries exported from a Sigma Analytics workbook.

Sigma generates SQL against the underlying data warehouse. Each query below represents one or more
dashboard elements. Extract the data model information needed to reverse-engineer the workbook.

SIGMA-EXPORTED SQL:
{sigma_sql}

Extract:
1. All source tables/views referenced (schema.table or just table names)
2. All columns queried — distinguish raw columns from calculated expressions
3. Aggregations used (SUM, COUNT, AVG, etc.) and what they measure
4. GROUP BY dimensions — these are the metrics' grouping keys
5. Any JOINs — these reveal relationships between source tables
6. Time/date columns and any truncation (DATE_TRUNC, TO_DATE, etc.) hinting at grain
7. The business domain this SQL is serving (RevOps, Finance, etc.)

Return JSON only:
{{
  "domain": "...",
  "dominant_grain": "monthly",
  "source_tables": ["schema.table_name"],
  "sigma_datasets": ["inferred dataset name from table names"],
  "visible_column_names": ["actual column names found in SQL"],
  "metrics": [
    {{
      "label": "inferred metric name from aggregation",
      "chart_type": "unknown",
      "dimensions": ["group_by_columns"],
      "time_grain": "inferred from date truncation",
      "aggregation": "SUM|COUNT|AVG|etc",
      "description": "plain English description",
      "sql_expression": "the exact aggregation expression"
    }}
  ],
  "joins": [
    {{"left": "table_a", "right": "table_b", "on": "join_condition"}}
  ],
  "sigma_calculations": []
}}"""


# ───────── Prompt 2: Schema mapping + Sigma repointing plan ─────────

_MAPPING_PROMPT_TEMPLATE = """\
You are a data modeling expert. A Sigma Analytics dashboard has been analyzed and the artifacts
below were extracted. Your task:

1. Map the Sigma dashboard's data requirements to the connected source schema
2. Design a dbt mart model that replaces the dashboard's direct warehouse queries
3. Generate a precise Sigma repointing plan so the dashboard can be switched to the new model

EXTRACTED SIGMA ARTIFACTS:
{metrics_json}

VISIBLE COLUMN NAMES: {visible_columns}
CURRENT SOURCE TABLES/DATASETS: {sigma_datasets}
DOMAIN: {domain}  |  GRAIN: {grain}

SOURCE DATABASE SCHEMA (what is actually in the connected warehouse):
{schema_summary}

Rules for dbt models:
- Staging SQL uses dbt {{{{ source('{source_db}', 'table_name') }}}} syntax
- Mart SQL uses dbt {{{{ ref('stg_model') }}}} syntax
- Mart model pre-aggregates where it makes the Sigma query simpler
- Column names in the mart should match (or improve on) what Sigma currently expects

Return JSON only, no prose:
{{
  "mart_name": "mart_{domain_snake}_summary",
  "grain": "one row per ... per month",
  "metric_mapping": [
    {{"label": "...", "source_tables": ["..."], "confidence": "high|medium|low"}}
  ],
  "staging_models": [
    {{"name": "stg_...", "source_table": "...", "sql": "select ...\\nfrom {{{{ source('{source_db}', '...') }}}}"}}
  ],
  "mart_sql": "select ...\\nfrom {{{{ ref('stg_...') }}}}\\n...",
  "schema_columns": [
    {{"name": "...", "description": "...", "type": "varchar|integer|numeric|timestamp|boolean", "nullable": true}}
  ],
  "sigma_repointing": {{
    "new_connection": {{
      "type": "Snowflake",
      "database": "{source_db}",
      "schema": "{source_db}_dw",
      "note": "The dbt target schema — contains the mart views/tables"
    }},
    "dataset_mapping": [
      {{
        "current_sigma_dataset": "...",
        "new_model": "mart_...",
        "model_type": "mart|staging",
        "grain_change": "pre-aggregated monthly vs raw rows",
        "notes": "..."
      }}
    ],
    "column_renames": [
      {{
        "current_name": "...",
        "new_name": "...",
        "reason": "normalized naming"
      }}
    ],
    "calculated_fields_to_migrate": [
      {{
        "sigma_formula": "...",
        "description": "what it computes",
        "disposition": "now_in_model|keep_in_sigma|simplifies_to_column"
      }}
    ]
  }}
}}"""


# ───────── Invocation functions ─────────

def _invoke_vision(image_data_url: str) -> dict[str, Any]:
    client = _bedrock_client()
    media_type, b64_str = _parse_data_url(image_data_url)

    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 2048,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": b64_str,
                        },
                    },
                    {"type": "text", "text": _VISION_PROMPT},
                ],
            }
        ],
    }
    resp = client.invoke_model(modelId=BEDROCK_MODEL_ID, body=json.dumps(body))
    data = json.loads(resp["body"].read())
    return json.loads(_strip_code_fence(data["content"][0]["text"]))


def _invoke_sql_analysis(sigma_sql: str) -> dict[str, Any]:
    """Analyze Sigma-exported SQL queries to extract data model information."""
    client = _bedrock_client()
    prompt = _SQL_ANALYSIS_PROMPT_TEMPLATE.format(sigma_sql=sigma_sql[:8000])
    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 2048,
        "messages": [{"role": "user", "content": prompt}],
    }
    resp = client.invoke_model(modelId=BEDROCK_MODEL_ID, body=json.dumps(body))
    data = json.loads(resp["body"].read())
    return json.loads(_strip_code_fence(data["content"][0]["text"]))


def _invoke_mapping(
    metrics: list[dict],
    domain: str,
    grain: str,
    schema_tables: list[dict],
    source_db: str,
    visible_columns: list[str],
    sigma_datasets: list[str],
    sigma_calculations: list[dict],
) -> dict[str, Any]:
    client = _bedrock_client()
    domain_snake = re.sub(r"[^a-z0-9]+", "_", domain.lower()).strip("_") or "data"

    # Merge any SQL-extracted calculations into the metrics list for the prompt
    all_metrics = metrics + [
        {
            "label": c.get("name", "calculation"),
            "chart_type": "calculated",
            "dimensions": [],
            "time_grain": "unknown",
            "aggregation": "formula",
            "description": c.get("description", c.get("formula", "")),
        }
        for c in sigma_calculations
    ]

    prompt = _MAPPING_PROMPT_TEMPLATE.format(
        metrics_json=json.dumps(all_metrics, indent=2),
        visible_columns=", ".join(visible_columns[:30]) or "none detected",
        sigma_datasets=", ".join(sigma_datasets[:10]) or "none detected",
        domain=domain,
        domain_snake=domain_snake,
        grain=grain,
        schema_summary=_schema_summary(schema_tables),
        source_db=source_db,
    )

    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 5000,
        "messages": [{"role": "user", "content": prompt}],
    }
    resp = client.invoke_model(modelId=BEDROCK_MODEL_ID, body=json.dumps(body))
    data = json.loads(resp["body"].read())
    return json.loads(_strip_code_fence(data["content"][0]["text"]))


# ───────── Public entry point ─────────

def analyze_dashboard(
    image_data_url: str,
    schema: dict,
    source_db: str,
    sigma_sql: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Analyze a Sigma dashboard screenshot (and optionally its exported SQL) against the source schema.

    When sigma_sql is provided it augments (not replaces) the vision analysis:
    the SQL gives precise column/table names that vision can miss, while vision
    gives chart types and UI context that SQL can't provide.

    Returns (vision_result, mapping_result). Raises on Bedrock errors.
    """
    tables = schema.get("tables", []) if isinstance(schema, dict) else []

    # Vision pass
    vision = _invoke_vision(image_data_url)

    # If the user provided exported Sigma SQL, merge its findings into vision
    if sigma_sql and sigma_sql.strip():
        try:
            sql_result = _invoke_sql_analysis(sigma_sql)
            # Merge: SQL wins on column names and source tables; vision wins on labels/chart types
            vision.setdefault("visible_column_names", [])
            vision["visible_column_names"] = list(set(
                vision.get("visible_column_names", []) + sql_result.get("visible_column_names", [])
            ))
            vision.setdefault("sigma_datasets", [])
            for t in sql_result.get("source_tables", []):
                if t not in vision["sigma_datasets"]:
                    vision["sigma_datasets"].append(t)
            # Supplement metrics: add SQL-derived metrics that weren't visible
            sql_labels = {m.get("label", "").lower() for m in sql_result.get("metrics", [])}
            vis_labels = {m.get("label", "").lower() for m in vision.get("metrics", [])}
            for m in sql_result.get("metrics", []):
                if m.get("label", "").lower() not in vis_labels:
                    vision.setdefault("metrics", []).append(m)
            # Merge joins info for the mapping call
            vision["sql_joins"] = sql_result.get("joins", [])
        except Exception as exc:
            logger.warning("SQL analysis pass failed (continuing with vision only): %s", exc)

    metrics = vision.get("metrics", [])
    domain = vision.get("domain", "Data")
    grain = vision.get("dominant_grain", "monthly")
    visible_columns = vision.get("visible_column_names", [])
    sigma_datasets = vision.get("sigma_datasets", [])
    sigma_calculations = vision.get("sigma_calculations", [])

    mapping = _invoke_mapping(
        metrics=metrics,
        domain=domain,
        grain=grain,
        schema_tables=tables,
        source_db=source_db,
        visible_columns=visible_columns,
        sigma_datasets=sigma_datasets,
        sigma_calculations=sigma_calculations,
    )
    return vision, mapping
