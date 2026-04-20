"""Step 3 (Logical Model) handler.

Emits a logical model where every field's data_type comes from the source's
information_schema (via scan_metadata) and sample_values come from a bounded
``SELECT … LIMIT 5`` via the driver.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal, cast
from uuid import UUID

from ..api.events import (
    ArtifactUpdateEvent,
    DoneEvent,
    LogicalField,
    LogicalModelPayload,
    LogicalTable,
    ToolResultEvent,
    ToolStartEvent,
)
from ._shared import ensure_driver, sanitize_id, scan_metadata_safe, source_id_for

if TYPE_CHECKING:
    from ..api.deps import SessionContext
    from ..api.routes_workflow import StepRequest
    from ..api.sse import SSEEmitter
    from ..api.zip_stream import ArtifactStore


async def run(
    request: StepRequest,
    session: SessionContext,
    emitter: SSEEmitter,
    run_id: UUID,
    artifact_store: ArtifactStore,
) -> None:
    assert request.connection is not None
    source_id = source_id_for(session, request.connection)
    driver = ensure_driver(source_id, request.connection)

    emitter.emit(
        ToolStartEvent(run_id=run_id, tool="scan_metadata", args_summary=f"source={source_id}")
    )
    metadata = scan_metadata_safe(source_id)
    raw_tables = metadata.get("tables", []) if isinstance(metadata, dict) else []
    emitter.emit(
        ToolResultEvent(run_id=run_id, tool="scan_metadata", summary=f"{len(raw_tables)} tables")
    )

    schema_prefix = request.connection.schema
    tables: list[LogicalTable] = []

    for raw in raw_tables[:6]:  # cap to keep MVP stream size bounded
        table_name = raw.get("name") or raw.get("table_name") or ""
        if not table_name:
            continue
        fq = f"{schema_prefix}.{table_name}" if schema_prefix else table_name
        columns = raw.get("columns") or []

        fields: list[LogicalField] = []
        for col in columns:
            col_name = col.get("name") or col.get("column_name") or ""
            if not col_name:
                continue
            samples = _sample_values(driver, fq, col_name)
            fields.append(
                LogicalField(
                    name=col_name,
                    data_type=col.get("data_type") or col.get("type") or "unknown",
                    nullable=bool(col.get("nullable", True)),
                    sample_values=samples,
                    is_measure=_looks_like_measure(col_name, col),
                    role=_infer_role(col_name, col),
                )
            )

        tables.append(
            LogicalTable(
                id=sanitize_id(table_name),
                label=table_name.replace("_", " ").title(),
                grain=None,
                fields=fields,
            )
        )

    emitter.emit(
        ArtifactUpdateEvent(
            run_id=run_id,
            step="logical",
            artifact_type="logical_model",
            payload=LogicalModelPayload(tables=tables),
        )
    )
    emitter.emit(DoneEvent(run_id=run_id, step="logical"))


def _sample_values(driver: Any, fq_table: str, column: str) -> list[str]:
    """Return up to 5 representative values. Best-effort; empty list on failure."""
    try:
        query_fn = getattr(driver, "run_query", None) or getattr(driver, "query", None)
        if query_fn is None:
            return []
        sql = f'SELECT DISTINCT "{column}" FROM {fq_table} LIMIT 5'
        result = cast(Any, query_fn(sql))
        rows = result.get("rows") if isinstance(result, dict) else result
        return [str(r[0]) if isinstance(r, (list, tuple)) else str(r) for r in rows or []][:5]
    except Exception:
        return []


def _looks_like_measure(col_name: str, col: dict[str, Any]) -> bool:
    dtype = (col.get("data_type") or col.get("type") or "").lower()
    name = col_name.lower()
    if any(t in dtype for t in ("int", "numeric", "decimal", "float", "double", "money")):
        return not name.endswith("_id") and name != "id"
    return False


def _infer_role(
    col_name: str, col: dict[str, Any]
) -> Literal["id", "dimension", "measure", "attribute"]:
    name = col_name.lower()
    if name == "id" or name.endswith("_id"):
        return "id"
    if _looks_like_measure(col_name, col):
        return "measure"
    dtype = (col.get("data_type") or col.get("type") or "").lower()
    if "date" in dtype or "time" in dtype:
        return "dimension"
    return "attribute"
