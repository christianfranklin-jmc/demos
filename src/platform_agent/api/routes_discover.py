"""POST /workflow/discover — post-connection business-process discovery.

Given a connected source, analyse the schema (tables, columns, FKs, row
counts) and return a structured snapshot the UI can use to ground itself in
the specific database the user just connected:

  - ``product_name``      — short title for the data product (ContextBar)
  - ``domain_summary``    — one-sentence classification (e.g. B2B wholesale)
  - ``business_processes`` — the distinct processes the schema supports, each
    with the tables, measures, and grain that makes it identifiable
  - ``suggested_questions`` — pills for Talk-to-Data, grounded in actual
    tables/columns (not a Northwinds-hardcoded list)
  - ``step_suggestions``  — per-step opener suggestions keyed by step number

Implementation is a single Bedrock Claude call over the scanned schema — no
data reads — so it's cheap and deterministic enough to fire immediately
after ``CONNECTION_SET`` on the frontend.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Annotated, Any
from uuid import UUID, uuid4

import boto3
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from ..workflow._shared import ensure_driver, scan_metadata_safe, source_id_for
from .deps import SessionContext, get_session_context
from .routes_workflow import SourceConnection

logger = logging.getLogger(__name__)

router = APIRouter()

BEDROCK_MODEL_ID = "us.anthropic.claude-sonnet-4-20250514-v1:0"
BEDROCK_REGION = "us-east-1"
DISCOVER_TIMEOUT_S = 60.0

# Per-process cache of discover payloads keyed by source_id. Shared with
# step handlers so the PRD can reuse the business-process analysis the
# frontend already paid for on connect.
_DISCOVERY_CACHE: dict[str, dict[str, Any]] = {}


def get_cached_discovery(source_id: str) -> dict[str, Any] | None:
    return _DISCOVERY_CACHE.get(source_id)


class DiscoverRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    connection: SourceConnection


class BusinessProcess(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    description: str
    key_tables: list[str] = Field(default_factory=list)
    measures: list[str] = Field(default_factory=list)
    grain: str | None = None


class DiscoverResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    run_id: UUID
    product_name: str
    domain_summary: str
    business_processes: list[BusinessProcess]
    suggested_questions: list[str]
    step_suggestions: dict[str, list[str]]


def _bedrock_client() -> Any:
    return boto3.client("bedrock-runtime", region_name=BEDROCK_REGION)


def _schema_payload(tables: list[dict[str, Any]], schema: str | None) -> str:
    """DDL-ish summary with row counts + FKs — compact but information-dense."""
    prefix = f"{schema}." if schema else ""
    lines: list[str] = []
    for t in tables:
        name = t.get("name") or t.get("table_name") or ""
        if not name:
            continue
        cols = t.get("columns") or []
        row_count = t.get("row_count", "?")
        col_list = ", ".join(
            f"{c.get('name', '?')} {c.get('data_type', '?')}"
            for c in cols
            if c.get("name") or c.get("column_name")
        )
        fks = t.get("foreign_keys") or []
        fk_list = "; ".join(
            f"{fk.get('column')}→{fk.get('references_table')}.{fk.get('references_column')}"
            for fk in fks
            if fk.get("column") and fk.get("references_table")
        )
        line = f"{prefix}{name} [{row_count} rows] ({col_list})"
        if fk_list:
            line += f"  FKs: {fk_list}"
        lines.append(line)
    return "\n".join(lines)


_SYSTEM_PROMPT = """You are a senior data architect. You are given the \
scanned schema of a database (tables, columns, foreign keys, row counts) \
and must classify the business domain it supports.

Return ONE JSON object, inside a ```json fenced block, with EXACTLY these keys:

- "product_name": short title (3-7 words) for a data product built on this \
  source, in the problem domain (e.g. "Northwinds Order & Sales Analytics", \
  "Pinnacle Client Portfolio Insights"). Do NOT use generic words like "Data \
  Platform" or "Analytics Product".
- "domain_summary": one-sentence description of what the database supports \
  (e.g. "B2B wholesale/retail distribution with full order-to-cash tracking").
- "business_processes": array of 3-6 objects, each {
    "name": short phrase (e.g. "Order Management"),
    "description": 1-2 sentences,
    "key_tables": [tables that drive this process — real table names only],
    "measures": [measurable columns found in those tables; empty array if none],
    "grain": short phrase describing transaction grain, or null
  }
- "suggested_questions": array of 5-6 plain-English questions a data \
  engineer would run on this specific source. Each must reference REAL \
  tables or columns from the schema, produce useful aggregates or joins, \
  and be answerable with a single SELECT. NO generic Northwinds examples.
- "step_suggestions": object with string keys "1","2","3","4" mapping to \
  an array of 4 suggestions each, tailored to what this source supports:
    1: requirements the PRD could address on this data (e.g. "Measure \
       order volume by territory and quarter")
    2: conceptual-model prompts ("Propose the orders fact and its \
       dimensions" — referencing real entities)
    3: logical-model prompts ("Build fct_orders at the line-item grain")
    4: delivery prompts ("Generate a dbt project with surrogate keys …")

Rules:
- Do NOT invent tables or columns. Ground every reference in the schema given.
- If the schema does not clearly match a classic pattern, describe what is \
  actually there.
- Keep descriptions concrete. Avoid buzzwords ("robust", "intuitive", \
  "comprehensive") and non-specific measures ("KPIs", "metrics").
- Output MUST be valid JSON inside the fenced block. No commentary outside."""


def _extract_json(text: str) -> dict[str, Any]:
    fence = re.search(r"```(?:json)?\s*(\{.+?\})\s*```", text, re.DOTALL)
    payload = fence.group(1) if fence else text.strip()
    try:
        return json.loads(payload)
    except json.JSONDecodeError as exc:
        logger.warning("discover: JSON parse failed: %s", exc)
        raise HTTPException(
            status_code=502, detail="Model returned unparseable JSON."
        ) from exc


def _invoke_bedrock(schema_ddl: str, driver_type: str) -> dict[str, Any]:
    client = _bedrock_client()
    user = (
        f"Driver: {driver_type}\n\n"
        f"SCANNED SCHEMA (table [row_count] columns, FKs):\n{schema_ddl}\n\n"
        f"Analyse the above and return the JSON payload described in the "
        f"system prompt."
    )
    resp = client.invoke_model(
        modelId=BEDROCK_MODEL_ID,
        body=json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 2500,
            "system": _SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": user}],
        }),
    )
    payload = json.loads(resp["body"].read())
    parts = payload.get("content", [])
    text = "".join(p.get("text", "") for p in parts if isinstance(p, dict))
    return _extract_json(text)


def _normalize_step_suggestions(raw: Any) -> dict[str, list[str]]:
    """Coerce the model's 'step_suggestions' into {"1".."4": [str,...]}."""
    out: dict[str, list[str]] = {"1": [], "2": [], "3": [], "4": []}
    if not isinstance(raw, dict):
        return out
    for key in ("1", "2", "3", "4"):
        value = raw.get(key) or raw.get(int(key))  # type: ignore[arg-type]
        if isinstance(value, list):
            out[key] = [str(v) for v in value if isinstance(v, (str, int))][:6]
    return out


@router.post("/workflow/discover", response_model=DiscoverResponse)
async def post_discover(
    body: DiscoverRequest,
    session: SessionContext = Depends(get_session_context),
    _x_dsa_session_id: Annotated[str | None, Header(alias="X-DSA-Session-ID")] = None,
) -> DiscoverResponse:
    run_id = uuid4()
    source_id = source_id_for(session, body.connection)
    ensure_driver(source_id, body.connection)

    metadata = scan_metadata_safe(source_id)
    tables = metadata.get("tables", []) if isinstance(metadata, dict) else []
    if not tables:
        raise HTTPException(status_code=400, detail="No tables discovered on the source.")

    schema_ddl = _schema_payload(tables, body.connection.schema)

    try:
        data = await asyncio.wait_for(
            asyncio.to_thread(_invoke_bedrock, schema_ddl, body.connection.driver_type),
            timeout=DISCOVER_TIMEOUT_S,
        )
    except asyncio.TimeoutError as exc:
        raise HTTPException(
            status_code=504, detail="Discovery timed out."
        ) from exc
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("discover failed: %s", exc)
        raise HTTPException(status_code=502, detail=f"Discovery failed: {exc}") from exc

    processes_raw = data.get("business_processes") or []
    processes: list[BusinessProcess] = []
    for item in processes_raw:
        if not isinstance(item, dict):
            continue
        try:
            processes.append(
                BusinessProcess(
                    name=str(item.get("name", "")).strip() or "Unnamed process",
                    description=str(item.get("description", "")).strip(),
                    key_tables=[str(t) for t in (item.get("key_tables") or []) if t],
                    measures=[str(m) for m in (item.get("measures") or []) if m],
                    grain=(str(item["grain"]).strip() if item.get("grain") else None),
                )
            )
        except Exception as exc:
            logger.warning("discover: skipping malformed process: %s", exc)

    suggested = data.get("suggested_questions") or []
    if not isinstance(suggested, list):
        suggested = []
    suggested = [str(q) for q in suggested if isinstance(q, (str, int))][:8]

    response = DiscoverResponse(
        run_id=run_id,
        product_name=str(data.get("product_name") or "Data Product").strip(),
        domain_summary=str(data.get("domain_summary") or "").strip(),
        business_processes=processes,
        suggested_questions=suggested,
        step_suggestions=_normalize_step_suggestions(data.get("step_suggestions")),
    )
    _DISCOVERY_CACHE[source_id] = response.model_dump(mode="json")
    return response


__all__ = ["router", "DiscoverRequest", "DiscoverResponse", "BusinessProcess"]
