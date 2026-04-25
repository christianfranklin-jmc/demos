"""POST /workflow/query — agent-driven NL→SQL on the session's connected source.

Delegates to the Strands agent (same pattern as streamlit_app/app.py): the
agent receives the question + discovered schema, calls ``run_query`` as many
times as needed (joining across tables, exploring values, self-correcting on
error), and returns a final narrative plus the SQL it actually executed.

Hard safety:
  * ``run_query`` only exposes SELECT execution (the tool enforces read-only
    via the driver). The agent system prompt tells it to avoid DDL/DML.
  * A post-hoc keyword check on the surfaced SQL rejects anything that
    somehow contains write keywords before the result leaves the server.
  * Row cap (250) is enforced on whatever rows the last successful query
    produced before they're returned to the client.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Annotated, Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from ..agent import create_agent
from ..workflow._shared import ensure_driver, scan_metadata_safe, source_id_for
from .deps import SessionContext, get_session_context
from .routes_workflow import SourceConnection

logger = logging.getLogger(__name__)

router = APIRouter()

MAX_ROWS = 250
AGENT_TIMEOUT_S = 90.0

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
    narrative: str = ""
    error: str | None = None


def _schema_context(tables: list[dict[str, Any]], schema: str | None, cap: int = 40) -> str:
    """Compact DDL-ish schema summary for the agent prompt."""
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
        fks = t.get("foreign_keys") or []
        fk_list = "; ".join(
            f"{fk.get('column')}→{fk.get('references_table')}.{fk.get('references_column')}"
            for fk in fks
            if fk.get("column") and fk.get("references_table")
        )
        line = f"{prefix}{name}({col_list})"
        if fk_list:
            line += f"  FKs: {fk_list}"
        lines.append(line)
    return "\n".join(lines)


def _extract_text(result: Any) -> str:
    """Pull the assistant's final narrative text from a Strands result."""
    msg = getattr(result, "message", None)
    if msg is None:
        return str(result)
    content = getattr(msg, "content", None)
    if content is None and isinstance(msg, dict):
        content = msg.get("content")
    if not isinstance(content, list):
        return str(result)
    texts = [
        block.get("text", "")
        for block in content
        if isinstance(block, dict) and "text" in block and block.get("text")
    ]
    return "\n".join(texts).strip() or str(result)


def _walk_messages(agent: Any, result: Any) -> list[Any]:
    """Return the full turn-history; prefer agent.messages if present."""
    history = getattr(agent, "messages", None)
    if isinstance(history, list) and history:
        return history
    msg = getattr(result, "message", None)
    return [msg] if msg else []


def _get_content(msg: Any) -> list[Any]:
    content = getattr(msg, "content", None)
    if content is None and isinstance(msg, dict):
        content = msg.get("content")
    return content if isinstance(content, list) else []


def _extract_last_run_query(
    agent: Any, result: Any
) -> tuple[str, list[str], list[list[Any]]]:
    """Walk tool_use/tool_result pairs and return the SQL + rows of the
    *most informative* ``run_query`` call — defined as the one that returned
    the most rows, with a late-query tie-breaker. Exploratory counts and
    DISTINCT probes are usually 1 row; the answering JOIN is many rows, and
    we want that one on the UI.

    Returns ``("", [], [])`` if no successful query ran.
    """

    successes: list[tuple[str, list[str], list[list[Any]], int]] = []

    # Map tool_use id → sql so we can pair with the corresponding tool_result.
    pending_sql: dict[str, str] = {}

    for msg in _walk_messages(agent, result):
        for block in _get_content(msg):
            if not isinstance(block, dict):
                continue
            # Strands uses either {"toolUse": {...}} / {"toolResult": {...}}
            # (Bedrock shape) or {"type": "tool_use"/"tool_result"} — handle both.
            tu = block.get("toolUse") or (block if block.get("type") == "tool_use" else None)
            tr = block.get("toolResult") or (
                block if block.get("type") == "tool_result" else None
            )

            if tu:
                name = tu.get("name") or tu.get("toolName")
                if name != "run_query":
                    continue
                tool_id = tu.get("toolUseId") or tu.get("id") or ""
                tool_input = tu.get("input") or {}
                sql = ""
                if isinstance(tool_input, dict):
                    sql = tool_input.get("sql") or ""
                elif isinstance(tool_input, str):
                    try:
                        parsed = json.loads(tool_input)
                        sql = parsed.get("sql", "") if isinstance(parsed, dict) else ""
                    except json.JSONDecodeError:
                        sql = ""
                if tool_id and sql:
                    pending_sql[tool_id] = sql

            if tr:
                tool_id = tr.get("toolUseId") or tr.get("id") or ""
                status = tr.get("status", "success")
                # Content may be [{"json": {...}}] or [{"text": "..."}] or a string.
                parsed = _parse_tool_result_payload(tr.get("content"))
                if not isinstance(parsed, dict):
                    continue
                rows = parsed.get("rows")
                if not isinstance(rows, list):
                    continue
                if status and status != "success":
                    continue
                sql = pending_sql.get(tool_id, "")
                cols = parsed.get("columns") or parsed.get("column_names") or []
                normalized: list[list[Any]] = []
                for r in rows:
                    if isinstance(r, (list, tuple)):
                        normalized.append(list(r))
                    elif isinstance(r, dict):
                        normalized.append([r.get(c) for c in cols])
                    else:
                        normalized.append([r])
                successes.append((sql, list(cols), normalized, len(normalized)))

    if not successes:
        return "", [], []

    # Pick the query with the most rows; break ties by preferring the last one
    # in conversation order (enumerate index).
    best_idx, best = max(
        enumerate(successes), key=lambda pair: (pair[1][3], pair[0])
    )
    sql, cols, rows_out, _ = best
    return sql, cols, rows_out


def _parse_tool_result_payload(content: Any) -> Any:
    """tool_result content can be a JSON string, a list of text/json blocks,
    or already a dict. Normalise to a dict when possible.
    """
    if content is None:
        return None
    if isinstance(content, dict):
        return content
    if isinstance(content, str):
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return None
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict):
                if "json" in block and isinstance(block["json"], dict):
                    return block["json"]
                text = block.get("text")
                if isinstance(text, str):
                    try:
                        return json.loads(text)
                    except json.JSONDecodeError:
                        continue
    return None


def _assert_safe_sql(sql: str) -> None:
    """Reject anything that isn't a read-only SELECT/CTE. Defensive — the
    agent is told to stay in SELECT land, but we validate the emitted SQL.
    """
    if not sql:
        return  # the agent may have answered without running SQL
    s = sql.strip()
    if not s.lower().startswith(("select", "with")):
        raise HTTPException(status_code=400, detail="Only SELECT/WITH statements are allowed.")
    if _WRITE_KEYWORDS.search(s):
        raise HTTPException(
            status_code=400, detail="Query contains forbidden DDL/DML keywords."
        )


def _build_prompt(source_id: str, schema_ddl: str, driver_type: str, question: str) -> str:
    return (
        f"The database is connected as source_id='{source_id}' (driver: {driver_type}).\n"
        f"Use the run_query tool to answer the user's question with real data.\n"
        f"You can call run_query more than once — explore the schema, check value "
        f"distributions, and join across tables as needed. When a query fails, "
        f"inspect the error and try again with a corrected SQL.\n"
        f"Rules: SELECT/WITH only. No writes. Cap results at {MAX_ROWS} rows per call. "
        f"Quote identifiers with the correct dialect for {driver_type}.\n\n"
        f"AVAILABLE SCHEMA:\n{schema_ddl}\n\n"
        f"When you have the answer, give a short plain-English summary of the finding "
        f"and reference the SQL you ran. Do not invent numbers — only report values "
        f"returned by run_query.\n\n"
        f"Question: {question}"
    )


def _invoke_agent(source_id: str, schema_ddl: str, driver_type: str, question: str) -> tuple[Any, Any]:
    """Build a query-only Strands agent and run it synchronously.

    Returns ``(agent, result)`` so the caller can walk the full message
    history via ``agent.messages``.
    """
    from ..tools.toolkit_query import run_query
    from ..tools.toolkit_scan import scan_metadata

    agent = create_agent(tools=[scan_metadata, run_query])
    prompt = _build_prompt(source_id, schema_ddl, driver_type, question)
    result = agent(prompt)
    return agent, result


@router.post("/workflow/query", response_model=QueryResponse)
async def post_query(
    body: QueryRequest,
    session: SessionContext = Depends(get_session_context),
    _x_dsa_session_id: Annotated[str | None, Header(alias="X-DSA-Session-ID")] = None,
) -> QueryResponse:
    run_id = uuid4()
    source_id = source_id_for(session, body.connection)
    ensure_driver(source_id, body.connection)

    metadata = scan_metadata_safe(source_id)
    tables = metadata.get("tables", []) if isinstance(metadata, dict) else []
    if not tables:
        raise HTTPException(status_code=400, detail="No tables discovered on the source.")
    schema_ddl = _schema_context(tables, body.connection.schema)

    try:
        agent, result = await asyncio.wait_for(
            asyncio.to_thread(
                _invoke_agent, source_id, schema_ddl, body.connection.driver_type, body.question
            ),
            timeout=AGENT_TIMEOUT_S,
        )
    except asyncio.TimeoutError as exc:
        logger.warning("agent query timed out after %ss", AGENT_TIMEOUT_S)
        raise HTTPException(
            status_code=504, detail="Agent query timed out; try a simpler question."
        ) from exc
    except Exception as exc:
        logger.exception("agent query failed: %s", exc)
        raise HTTPException(status_code=502, detail=f"Agent error: {exc}") from exc

    narrative = _extract_text(result)
    sql, columns, rows = _extract_last_run_query(agent, result)
    _assert_safe_sql(sql)

    truncated = len(rows) > MAX_ROWS
    if truncated:
        rows = rows[:MAX_ROWS]

    error: str | None = None
    if not sql and not rows:
        # Agent answered without running SQL — flag it so the UI can show the
        # narrative even though there's no table to render.
        error = "Agent did not execute a query; see narrative for the response."

    return QueryResponse(
        question=body.question,
        generated_sql=sql,
        columns=columns,
        rows=rows,
        row_count=len(rows),
        truncated=truncated,
        run_id=run_id,
        narrative=narrative,
        error=error,
    )


__all__ = ["router", "QueryRequest", "QueryResponse"]
