"""Dashboard screenshot analysis using Bedrock vision.

Two LLM calls:
1. Vision extraction — extract metrics, chart types, and dimensions from screenshot.
2. Schema mapping — map extracted metrics to source tables and generate dbt SQL.
"""
from __future__ import annotations

import base64
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
    media_type = header.split(";")[0][len("data:"):]  # e.g. "image/jpeg"
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


_VISION_PROMPT = """\
Analyze this BI dashboard screenshot for data engineering purposes.

Extract every visible metric, KPI, and chart. For each one identify:
- label: exact text label as shown on the dashboard
- chart_type: bar, line, kpi_tile, table, scatter, pie, area, or combo
- dimensions: list of grouping dimensions visible (axis labels, legend, column headers)
- time_grain: daily, weekly, monthly, quarterly, annual, or unknown
- aggregation: sum, count, average, percent, or ratio
- description: plain English explanation of what this measures

Also identify:
- domain: business area (e.g. RevOps, Finance, Marketing, HR, Operations, Sales)
- dominant_grain: the most common time grain across the dashboard

Return JSON only, no prose:
{
  "domain": "...",
  "dominant_grain": "monthly",
  "metrics": [
    {
      "label": "...",
      "chart_type": "...",
      "dimensions": ["..."],
      "time_grain": "...",
      "aggregation": "...",
      "description": "..."
    }
  ]
}"""


_MAPPING_PROMPT_TEMPLATE = """\
You are a data modeling expert. A BI dashboard was analyzed and the metrics below were extracted.
Map them to the connected database schema and design a dbt mart model.

EXTRACTED DASHBOARD METRICS:
{metrics_json}

DOMAIN: {domain}  |  DOMINANT TIME GRAIN: {grain}

SOURCE DATABASE SCHEMA:
{schema_summary}

Design the simplest dimensional model to power this dashboard.

Rules:
- Staging SQL must use dbt {{{{ source('{source_db}', 'table_name') }}}} syntax
- Mart SQL must use dbt {{{{ ref('stg_model') }}}} syntax
- Generate SQL that could actually run against the schema above
- Keep staging models as thin pass-throughs; mart model does the joins and aggregations

Return JSON only, no prose:
{{
  "mart_name": "mart_{domain_snake}_summary",
  "grain": "description of one row",
  "metric_mapping": [
    {{"label": "...", "source_tables": ["..."], "confidence": "high|medium|low"}}
  ],
  "staging_models": [
    {{"name": "stg_...", "source_table": "...", "sql": "select *\\nfrom {{{{ source('{source_db}', '...') }}}}"}}
  ],
  "mart_sql": "select ...\\nfrom {{{{ ref('stg_...') }}}}\\n...",
  "schema_columns": [
    {{"name": "...", "description": "...", "type": "varchar|integer|numeric|timestamp|boolean", "nullable": true}}
  ]
}}"""


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


def _invoke_mapping(
    metrics: list[dict],
    domain: str,
    grain: str,
    schema_tables: list[dict],
    source_db: str,
) -> dict[str, Any]:
    client = _bedrock_client()
    domain_snake = re.sub(r"[^a-z0-9]+", "_", domain.lower()).strip("_") or "data"

    prompt = _MAPPING_PROMPT_TEMPLATE.format(
        metrics_json=json.dumps(metrics, indent=2),
        domain=domain,
        domain_snake=domain_snake,
        grain=grain,
        schema_summary=_schema_summary(schema_tables),
        source_db=source_db,
    )

    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 4096,
        "messages": [{"role": "user", "content": prompt}],
    }
    resp = client.invoke_model(modelId=BEDROCK_MODEL_ID, body=json.dumps(body))
    data = json.loads(resp["body"].read())
    return json.loads(_strip_code_fence(data["content"][0]["text"]))


def analyze_dashboard(
    image_data_url: str,
    schema: dict,
    source_db: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Analyze a dashboard screenshot against the source schema.

    Returns (vision_result, mapping_result). Raises on Bedrock errors or
    unparseable JSON — callers should wrap in try/except and emit a fallback.
    """
    tables = schema.get("tables", []) if isinstance(schema, dict) else []
    vision = _invoke_vision(image_data_url)
    metrics = vision.get("metrics", [])
    domain = vision.get("domain", "Data")
    grain = vision.get("dominant_grain", "monthly")
    mapping = _invoke_mapping(metrics, domain, grain, tables, source_db)
    return vision, mapping
