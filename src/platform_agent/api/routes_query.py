"""POST /workflow/query — natural-language to SQL on the session's connected source.

Given the active connection and a plain-English question, use Bedrock
Claude to translate to a single SELECT statement grounded in the real
scanned schema, execute it via the driver, and return the rows.

Hard safety:
  * Only SELECT statements are accepted — anything that contains other
    DML/DDL keywords is rejected before execution.
  * One statement per request. Multiple statements are rejected.
  * Row cap (250) is enforced server-side so accidental full-table
    scans don't stall the UI.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Annotated, Any, Literal
from uuid import UUID, uuid4

import boto3
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from ..workflow._shared import ensure_driver, scan_metadata_safe, source_id_for
from .deps import SessionContext, get_session_context
from .routes_workflow import SourceConnection

logger = logging.getLogger(__name__)

router = APIRouter()

MAX_ROWS = 250
BEDROCK_MODEL_ID = "us.anthropic.claude-sonnet-4-20250514-v1:0"
BEDROCK_REGION = "us-east-1"

_WRITE_KEYWORDS = re.compile(
    r"\b(insert|update|delete|drop|truncate|alter|create|grant|revoke|"
    r"merge|replace|call|execute|copy)\b",
    re.IGNORECASE,
)


class QueryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=1, max_length=1000)
    connection: SourceConnection


class QueryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str
    generated_sql: str
    columns: list[str]
    rows: list[list[Any]]
    row_count: int
    truncated: bool
    run_id: UUID
    error: str | None = None


def _bedrock_client() -> Any:
    return boto3.client("bedrock-runtime", region_name=BEDROCK_REGION)


def _schema_context(tables: list[dict[str, Any]], schema: str | None, cap: int = 40) -> str:
    """Compact schema prompt — DDL-ish summary, capped to keep context small."""
    lines: list[str] = []
    prefix = f"{schema}." if schema else ""
    for t in tables[:cap]:
        name = t.get("name") or t.get("table_name") or ""
        if not name:
            continue
        cols = t.get("columns") or []
        col_list = ", ".join(
            f"{c.get('name', '?')} {c.get('data_type', '?')}"
            for c in cols
            if c.get("name") or c.get("column_name")
        )
        lines.append(f"{prefix}{name}({col_list})")
    return "\n".join(lines)


def _extract_sql(response_text: str) -> str:
    """Pull a SQL statement out of the model's reply.

    Claude tends to emit SQL inside ```sql ... ``` fences. Fall back to
    the raw text if no fence is present.
    """
    fence = re.search(r"```(?:sql)?\s*(.+?)```", response_text, re.IGNORECASE | re.DOTALL)
    sql = (fence.group(1) if fence else response_text).strip()
    # Strip leading narrative sentences that sometimes precede the SQL.
    idx = sql.lower().find("select")
    if idx > 0:
        sql = sql[idx:]
    return sql.strip().rstrip(";").strip()


def _assert_safe_select(sql: str) -> None:
    """Reject anything that isn't a single read-only SELECT."""
    if not sql:
        raise HTTPException(status_code=400, detail="Model returned no SQL.")
    if ";" in sql:
        raise HTTPException(status_code=400, detail="Only one statement per query is allowed.")
    if not sql.strip().lower().startswith(("select", "with")):
        raise HTTPException(status_code=400, detail="Only SELECT / WITH statements are allowed.")
    if _WRITE_KEYWORDS.search(sql):
        raise HTTPException(status_code=400, detail="Query contains forbidden DDL/DML keywords.")


def _translate_nl_to_sql(question: str, schema_ddl: str, driver_type: str) -> str:
    """Call Bedrock Claude to translate the question into a SELECT statement."""
    system = (
        "You are a careful SQL analyst. Translate the user's question into a SINGLE "
        f"{driver_type.upper()}-compatible SELECT statement using only the tables and "
        "columns below. Do NOT output commentary — reply with SQL only, "
        "inside a ```sql fenced block. If the question cannot be answered with a "
        "single SELECT, reply with a SELECT that returns an error message column.\n\n"
        f"AVAILABLE SCHEMA:\n{schema_ddl}\n\n"
        "Rules: LIMIT 250 at most. No writes, no DDL, no multi-statement scripts."
    )
    client = _bedrock_client()
    resp = client.invoke_model(
        modelId=BEDROCK_MODEL_ID,
        body=json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 1000,
            "system": system,
            "messages": [{"role": "user", "content": question}],
        }),
    )
    payload = json.loads(resp["body"].read())
    parts = payload.get("content", [])
    text = "".join(p.get("text", "") for p in parts if isinstance(p, dict))
    return _extract_sql(text)


def _run_sql(driver: Any, sql: str) -> tuple[list[str], list[list[Any]]]:
    """Execute the SELECT via the driver. Returns (columns, rows).

    The DatabaseDriver protocol exposes `execute_query(sql, max_rows)` — we
    rely on it (not `run_query`, which is the name used by the Strands
    `@tool` wrapper but not the driver itself).
    """
    # Belt-and-suspenders row cap: wrap the model's SQL in a subquery with a
    # hard LIMIT. Works on PostgreSQL, Redshift, and Snowflake (standard SQL).
    wrapped = f"SELECT * FROM ({sql}) AS _q LIMIT {MAX_ROWS + 1}"
    result = driver.execute_query(wrapped, max_rows=MAX_ROWS + 1)
    if not isinstance(result, dict):
        raise HTTPException(500, "Driver returned unexpected shape from execute_query")
    columns = result.get("columns") or result.get("column_names") or []
    rows = result.get("rows") or []
    normalized: list[list[Any]] = []
    for r in rows:
        if isinstance(r, (list, tuple)):
            normalized.append(list(r))
        elif isinstance(r, dict):
            normalized.append([r.get(c) for c in columns])
        else:
            normalized.append([r])
    return list(columns), normalized


@router.post("/workflow/query", response_model=QueryResponse)
async def post_query(
    body: QueryRequest,
    session: SessionContext = Depends(get_session_context),
    _x_dsa_session_id: Annotated[str | None, Header(alias="X-DSA-Session-ID")] = None,
) -> QueryResponse:
    run_id = uuid4()
    source_id = source_id_for(session, body.connection)
    driver = ensure_driver(source_id, body.connection)

    metadata = scan_metadata_safe(source_id)
    tables = metadata.get("tables", []) if isinstance(metadata, dict) else []
    if not tables:
        raise HTTPException(status_code=400, detail="No tables discovered on the source.")

    schema_ddl = _schema_context(tables, body.connection.schema)

    try:
        sql = _translate_nl_to_sql(body.question, schema_ddl, body.connection.driver_type)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("NL→SQL translation failed: %s", exc)
        raise HTTPException(status_code=502, detail=f"Translation failed: {exc}") from exc

    _assert_safe_select(sql)

    try:
        columns, rows = _run_sql(driver, sql)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("query execution failed: %s", exc)
        return QueryResponse(
            question=body.question,
            generated_sql=sql,
            columns=[],
            rows=[],
            row_count=0,
            truncated=False,
            run_id=run_id,
            error=f"{type(exc).__name__}: {exc}",
        )

    truncated = len(rows) > MAX_ROWS
    if truncated:
        rows = rows[:MAX_ROWS]
    return QueryResponse(
        question=body.question,
        generated_sql=sql,
        columns=columns,
        rows=rows,
        row_count=len(rows),
        truncated=truncated,
        run_id=run_id,
    )


__all__ = ["router", "QueryRequest", "QueryResponse"]
