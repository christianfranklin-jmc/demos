"""Dashboard reverse-engineering step handler.

Accepts a dashboard screenshot, analyzes it via Bedrock vision, maps the
extracted metrics to the connected source schema, and delivers a dbt project zip.
"""
from __future__ import annotations

import asyncio
import io
import logging
import os
import tempfile
import zipfile
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import UUID

from ..api.events import (
    ArtifactReadyEvent,
    ArtifactUpdateEvent,
    DetailedField,
    DetailedRequirementsPayload,
    DetailedTable,
    MessageEvent,
    ToolProgressEvent,
    ToolResultEvent,
    ToolStartEvent,
)
from ._shared import ensure_driver, scan_metadata_safe, source_id_for
from .dashboard_analyzer import analyze_dashboard

if TYPE_CHECKING:
    from ..api.deps import SessionContext
    from ..api.routes_dashboard import DashboardRequest
    from ..api.sse import SSEEmitter
    from ..api.zip_stream import ArtifactStore

logger = logging.getLogger(__name__)


async def run(
    request: DashboardRequest,
    session: SessionContext,
    emitter: SSEEmitter,
    run_id: UUID,
    artifact_store: ArtifactStore,
) -> None:
    source_id = source_id_for(session, request.connection)
    ensure_driver(source_id, request.connection)

    # 1 — Scan source schema
    emitter.emit(ToolStartEvent(
        run_id=run_id, tool="scan_metadata", args_summary=f"source={source_id}"
    ))
    metadata = scan_metadata_safe(source_id)
    raw_tables = metadata.get("tables", [])
    source_tables = [t.get("name") or t.get("table_name", "") for t in raw_tables]
    source_tables = [t for t in source_tables if t]
    emitter.emit(ToolResultEvent(
        run_id=run_id, tool="scan_metadata",
        summary=f"{len(source_tables)} source tables found",
    ))

    # 2 — Vision analysis + schema mapping (blocking Bedrock calls, run off-thread)
    emitter.emit(ToolStartEvent(
        run_id=run_id, tool="analyze_dashboard",
        args_summary="vision extraction + schema mapping via Bedrock",
    ))
    emitter.emit(MessageEvent(run_id=run_id, delta=False, content="Reading the dashboard..."))

    try:
        vision, mapping = await asyncio.to_thread(
            analyze_dashboard,
            request.image_data,
            metadata,
            request.connection.database,
        )
    except Exception as exc:
        logger.warning("dashboard analysis failed: %s", exc)
        emitter.emit(MessageEvent(
            run_id=run_id, delta=False,
            content=f"Could not fully analyze the image ({exc}). Generating a baseline dbt project from the source schema.",
        ))
        vision = {"domain": "Data", "dominant_grain": "monthly", "metrics": []}
        mapping = {
            "mart_name": f"mart_{request.connection.database.lower()}_summary",
            "grain": "unknown",
            "staging_models": [],
            "mart_sql": "",
            "schema_columns": [],
            "metric_mapping": [],
        }

    metrics = vision.get("metrics", [])
    domain = vision.get("domain", "Data")
    grain = vision.get("dominant_grain", "monthly")
    metric_mapping = mapping.get("metric_mapping", [])

    # Narrate what we found
    if metrics:
        labels = [m.get("label", "") for m in metrics[:4]]
        high_conf = sum(1 for m in metric_mapping if m.get("confidence") == "high")
        med_conf = sum(1 for m in metric_mapping if m.get("confidence") == "medium")
        narration = (
            f"I can see **{len(metrics)} metrics** in this {domain} dashboard: "
            + ", ".join(labels)
            + (f", and {len(metrics) - 4} more" if len(metrics) > 4 else "")
            + f". Dominant grain: **{grain}**. "
            + f"Schema mapping confidence — {high_conf} high, {med_conf} medium. "
            + "Building the dbt project now..."
        )
    else:
        narration = (
            f"Analyzing your {domain} dashboard against {len(source_tables)} source tables. "
            "Building the dbt project..."
        )

    emitter.emit(ToolResultEvent(
        run_id=run_id, tool="analyze_dashboard",
        summary=f"{len(metrics)} metrics, {domain} domain, {grain} grain",
    ))
    emitter.emit(MessageEvent(run_id=run_id, delta=False, content=narration))

    # 3 — Generate dbt project
    mart_name = mapping.get("mart_name") or f"mart_{domain.lower().replace(' ', '_')}_summary"
    staging_raw = mapping.get("staging_models", [])
    mart_sql = mapping.get("mart_sql", "")

    staging_models: list[dict] = []
    if staging_raw:
        for m in staging_raw:
            name = m.get("name") or (f"stg_{m.get('source_table', 'unknown')}" if m.get("source_table") else None)
            sql = m.get("sql", "")
            if name:
                staging_models.append({"name": name, "sql": sql})
    if not staging_models:
        staging_models = [
            {
                "name": f"stg_{t}",
                "sql": f"select *\nfrom {{{{ source('{request.connection.database}', '{t}') }}}}",
            }
            for t in source_tables[:8]
        ]

    mart_models: list[dict] = []
    if mart_sql and mart_name:
        mart_models = [{"name": mart_name, "sql": mart_sql, "materialized": "table"}]

    emitter.emit(ToolProgressEvent(
        run_id=run_id, tool="generate_dbt_project",
        note=f"{len(staging_models)} staging + {len(mart_models)} mart models",
    ))

    project_name = f"{request.connection.database.lower()}_dw"
    with tempfile.TemporaryDirectory() as tmpdir:
        from ..tools.dbt_generate import generate_dbt_project
        from ..tools.semantic_layer import generate_semantic_layer

        output_dir = os.path.join(tmpdir, project_name)
        generate_dbt_project(
            project_name=project_name,
            target_schema=project_name,
            source_database=request.connection.database,
            source_schema=request.connection.schema or "public",
            source_tables=source_tables[:10],
            staging_models=staging_models,
            mart_models=mart_models,
            output_dir=output_dir,
        )
        try:
            generate_semantic_layer(
                project_name=project_name,
                semantic_models=[],
                metrics=[],
                output_dir=output_dir,
            )
        except Exception as exc:
            logger.debug("semantic_layer skipped: %s", exc)

        zip_bytes = _zip_directory(output_dir)

    file_count = _count_zip_entries(zip_bytes)
    emitter.emit(ToolResultEvent(
        run_id=run_id, tool="generate_dbt_project",
        summary=f"{file_count} files, {_human(len(zip_bytes))}",
    ))

    # 4 — Emit artifact preview + terminal events
    preview = _build_preview(mapping, raw_tables)
    emitter.emit(ArtifactUpdateEvent(
        run_id=run_id,
        step="detailed",
        artifact_type="detailed_requirements",
        payload=preview,
    ))

    handle, entry = await artifact_store.register(zip_bytes, session.session_id)
    ttl_seconds = max(1, int(
        (entry.expires_at - entry.expires_at.__class__.now(entry.expires_at.tzinfo)).total_seconds()
    ))

    emitter.emit(MessageEvent(
        run_id=run_id, delta=False,
        content=(
            f"Generated **{file_count} files** ({_human(len(zip_bytes))}) — "
            f"{len(staging_models)} staging models"
            + (f" and `{mart_name}`" if mart_models else "")
            + ". Downloading now — unzip and run `dbt compile` to verify."
        ),
    ))
    emitter.emit(ArtifactReadyEvent(
        run_id=run_id,
        handle=handle,
        size_bytes=len(zip_bytes),
        file_count=file_count,
        expires_in_s=ttl_seconds,
        download_url=f"/workflow/artifact/{handle}",
    ))


# ───────── helpers ─────────


def _zip_directory(root: str) -> bytes:
    buf = io.BytesIO()
    root_path = Path(root)
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in root_path.rglob("*"):
            if path.is_file():
                zf.write(path, arcname=str(path.relative_to(root_path.parent)))
    return buf.getvalue()


def _count_zip_entries(zip_bytes: bytes) -> int:
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        return len(zf.namelist())


def _human(n: int) -> str:
    for unit in ("B", "KB", "MB"):
        if n < 1024 or unit == "MB":
            return (
                f"{n:.0f} {unit}" if unit == "B"
                else f"{n / 1024:.1f} {unit}" if unit == "KB"
                else f"{n / 1024 / 1024:.1f} {unit}"
            )
        n //= 1024
    return f"{n} GB"


def _build_preview(mapping: dict, raw_tables: list) -> DetailedRequirementsPayload:
    mart_name = mapping.get("mart_name", "mart_summary")
    grain = mapping.get("grain", "unknown")
    schema_columns = mapping.get("schema_columns", [])

    fact_fields = [
        DetailedField(
            target_field=col.get("name", ""),
            data_type=col.get("type", "varchar"),
            source_field=col.get("name"),
        )
        for col in schema_columns[:12]
        if col.get("name")
    ]
    fact = DetailedTable(table_name=mart_name, grain=grain, fields=fact_fields)

    seen: set[str] = set()
    dims: list[DetailedTable] = []
    for mm in mapping.get("metric_mapping", [])[:5]:
        for t in mm.get("source_tables", []):
            if t not in seen:
                seen.add(t)
                dims.append(DetailedTable(table_name=f"dim_{t}", grain=None, fields=[]))

    staging_names = [m.get("name", "") for m in mapping.get("staging_models", []) if m.get("name")]
    return DetailedRequirementsPayload(
        fact_table=fact,
        dimension_tables=dims,
        staging_models=staging_names,
        file_count=0,
    )
