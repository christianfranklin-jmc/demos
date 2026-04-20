"""Step 2 (Conceptual Model) handler.

Builds entities and relationships from the scanned FK graph. Snowflake
fallback applies naming-heuristic inference with ``inferred=True``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID

from ..api.events import (
    ArtifactUpdateEvent,
    ConceptualModelPayload,
    DoneEvent,
    Entity,
    Relationship,
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
    ensure_driver(source_id, request.connection)

    emitter.emit(
        ToolStartEvent(run_id=run_id, tool="scan_metadata", args_summary=f"source={source_id}")
    )
    metadata = scan_metadata_safe(source_id)
    tables = metadata.get("tables", []) if isinstance(metadata, dict) else []
    fks = metadata.get("foreign_keys", []) if isinstance(metadata, dict) else []

    entities = _build_entities(tables, request.connection.schema)
    relationships = _build_relationships(
        fks, entities, fallback_heuristic=(request.connection.driver_type == "snowflake")
    )

    emitter.emit(
        ToolResultEvent(
            run_id=run_id,
            tool="scan_metadata",
            summary=f"{len(entities)} entities, {len(relationships)} relationships",
        )
    )

    emitter.emit(
        ArtifactUpdateEvent(
            run_id=run_id,
            step="conceptual",
            artifact_type="conceptual_model",
            payload=ConceptualModelPayload(entities=entities, relationships=relationships),
        )
    )
    emitter.emit(DoneEvent(run_id=run_id, step="conceptual"))


def _build_entities(tables: list[dict[str, Any]], schema: str | None) -> list[Entity]:
    out: list[Entity] = []
    for t in tables:
        name = t.get("name") or t.get("table_name") or ""
        if not name:
            continue
        fq = f"{schema}.{name}" if schema else name
        pk = t.get("primary_key") or t.get("primary_keys") or []
        if isinstance(pk, str):
            pk = [pk]
        out.append(
            Entity(
                id=sanitize_id(name),
                label=name.replace("_", " ").title(),
                source_table=fq,
                row_count_est=t.get("row_count"),
                key_columns=list(pk) if pk else [],
            )
        )
    return out


def _build_relationships(
    fks: list[dict[str, Any]],
    entities: list[Entity],
    fallback_heuristic: bool,
) -> list[Relationship]:
    by_label: dict[str, str] = {e.source_table.split(".")[-1].lower(): e.id for e in entities}
    out: list[Relationship] = []

    for fk in fks:
        src = (fk.get("from_table") or fk.get("source_table") or "").lower()
        dst = (fk.get("to_table") or fk.get("target_table") or "").lower()
        if not src or not dst:
            continue
        src_id = by_label.get(src)
        dst_id = by_label.get(dst)
        if not src_id or not dst_id:
            continue
        out.append(
            Relationship(
                from_entity_id=src_id,
                to_entity_id=dst_id,
                from_column=fk.get("from_column") or fk.get("source_column") or "",
                to_column=fk.get("to_column") or fk.get("target_column") or "",
                cardinality="N:1",
                inferred=False,
            )
        )

    if not out and fallback_heuristic:
        # Snowflake often lacks declared FKs — infer from naming patterns.
        for e in entities:
            for f_col in e.key_columns:
                # Heuristic: "<something>_id" columns point at "<something>" entity.
                if f_col.endswith("_id") and f_col.lower() != "id":
                    base = f_col[:-3]
                    target = by_label.get(base) or by_label.get(base + "s")
                    if target and target != e.id:
                        out.append(
                            Relationship(
                                from_entity_id=e.id,
                                to_entity_id=target,
                                from_column=f_col,
                                to_column="id",
                                cardinality="N:1",
                                inferred=True,
                            )
                        )
    return out
