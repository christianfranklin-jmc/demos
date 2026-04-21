"""Step 1 (Requirements / PRD) handler.

Connects to the source database, scans metadata, and emits a PRD grounded in
the real tables discovered. This implementation is schema-driven (not LLM-
driven) to keep the MVP deterministic for integration tests. Later iterations
can layer a Strands agent call on top to enrich the prose.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID

from ..api.events import (
    ArtifactUpdateEvent,
    DoneEvent,
    MessageEvent,
    PrdPayload,
    PrdSection,
    ToolResultEvent,
    ToolStartEvent,
)
from ._shared import (
    ensure_driver,
    scan_metadata_safe,
    short_summary,
    source_id_for,
)

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
    assert request.connection is not None, "step 1 requires a connection"
    source_id = source_id_for(session, request.connection)

    emitter.emit(
        ToolStartEvent(
            run_id=run_id,
            tool="connect_to_database",
            args_summary=f"driver={request.connection.driver_type}",
        )
    )
    ensure_driver(source_id, request.connection)
    emitter.emit(
        ToolResultEvent(
            run_id=run_id, tool="connect_to_database", summary=f"connected to {source_id}"
        )
    )

    emitter.emit(
        ToolStartEvent(run_id=run_id, tool="scan_metadata", args_summary=f"source={source_id}")
    )
    metadata = scan_metadata_safe(source_id)
    tables = metadata.get("tables", []) if isinstance(metadata, dict) else []
    emitter.emit(
        ToolResultEvent(
            run_id=run_id,
            tool="scan_metadata",
            summary=f"Found {len(tables)} tables",
        )
    )

    payload = _build_prd(request.user_message, tables, request.connection.schema)
    emitter.emit(
        ArtifactUpdateEvent(
            run_id=run_id,
            step="requirements",
            artifact_type="prd",
            payload=payload,
        )
    )
    # Closing message varies with the user's intent so repeated turns don't
    # produce identical-looking chat replies. First sentence echoes the user's
    # prompt; second gives a quick count. Accumulated PRD content is visible
    # in the right-hand panel via APPEND_PRD.
    cited = [t for s in payload.sections for t in s.cited_tables][:6]
    prompt_preview = request.user_message.strip()
    if len(prompt_preview) > 80:
        prompt_preview = prompt_preview[:77] + "…"
    emitter.emit(
        MessageEvent(
            run_id=run_id,
            delta=False,
            content=(
                f"Captured **{prompt_preview}** into the PRD. "
                f"Grounded in {len(tables)} source tables; "
                f"top candidate entities: {', '.join(f'`{t}`' for t in cited) or 'none yet'}. "
                "Pick another refinement or approve the gate to move to Step 2."
            ),
        )
    )
    emitter.emit(DoneEvent(run_id=run_id, step="requirements"))


def _build_prd(user_message: str, tables: list[dict[str, Any]], schema: str | None) -> PrdPayload:
    """Assemble a PRD that cites real tables discovered by scan_metadata."""
    schema_prefix = f"{schema}." if schema else ""

    # Rank tables: entity-shaped (single-column PK + meaningful row count)
    # first, junction tables and empty tables last. Biggest entities surface
    # to the top so Orders / Customers / Products lead the citations rather
    # than alphabetical noise like customer_customer_demo.
    def rank(t: dict[str, Any]) -> tuple[int, int]:
        pk = t.get("primary_keys") or t.get("primary_key") or []
        if isinstance(pk, str):
            pk = [pk]
        junction_penalty = 1 if len(pk) >= 2 else 0  # junction → sort down
        rows = int(t.get("row_count") or 0)
        # Sort ascending on (junction_penalty, -rows) → junctions last, big rows first
        return (junction_penalty, -rows)

    ranked = sorted(tables, key=rank)
    table_refs = [
        f"{schema_prefix}{t.get('name', t.get('table_name', ''))}"
        for t in ranked
    ]
    table_refs = [ref for ref in table_refs if ref.strip(".")]
    cited = table_refs[:6]

    sections: list[PrdSection] = []
    sections.append(
        PrdSection(
            heading="Problem Statement",
            body=short_summary(user_message, 400),
            cited_tables=cited,
            completeness_contribution=0.20,
        )
    )
    sections.append(
        PrdSection(
            heading="Discovered Source Entities",
            body=(
                f"Scan of the connected source discovered {len(tables)} tables. "
                f"The candidate entity set for the data product is: "
                + ", ".join(f"`{t}`" for t in cited)
                + "."
            ),
            cited_tables=cited,
            completeness_contribution=0.30,
        )
    )
    sections.append(
        PrdSection(
            heading="Proposed Goals",
            body=(
                "Deliver a governed analytical data product atop the discovered source entities, "
                "with a Kimball-style star schema, dbt transformations, and a semantic layer for "
                "downstream BI."
            ),
            cited_tables=cited,
            completeness_contribution=0.25,
        )
    )
    sections.append(
        PrdSection(
            heading="Out of Scope",
            body=(
                "Operational source-system changes. Data capture layer. Real-time ingestion. "
                "User authentication for downstream consumers."
            ),
            cited_tables=[],
            completeness_contribution=0.0,
        )
    )

    completeness = min(1.0, sum(s.completeness_contribution for s in sections))
    return PrdPayload(sections=sections, completeness=completeness)
