"""Dashboard reverse-engineering step handler.

Accepts a Sigma dashboard screenshot (+ optional exported SQL), analyzes it via
Bedrock vision and/or SQL introspection, maps the extracted metrics to the connected
source schema, and delivers a dbt project zip that includes a SIGMA_REPOINTING_GUIDE.md.
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
    workbook_label = request.sigma_workbook_name or "Sigma dashboard"
    has_sql = bool(request.sigma_sql and request.sigma_sql.strip())
    analysis_summary = "vision extraction + schema mapping via Bedrock"
    if has_sql:
        analysis_summary += " (+ Sigma SQL export)"

    emitter.emit(ToolStartEvent(
        run_id=run_id, tool="analyze_dashboard", args_summary=analysis_summary,
    ))
    emitter.emit(MessageEvent(
        run_id=run_id, delta=False,
        content=f"Reading **{workbook_label}**..." + (" I can see Sigma SQL too — merging both." if has_sql else ""),
    ))

    try:
        vision, mapping = await asyncio.to_thread(
            analyze_dashboard,
            request.image_data,
            metadata,
            request.connection.database,
            request.sigma_sql,
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
    sigma_repointing = mapping.get("sigma_repointing", {})

    # Use detected workbook name if not supplied by caller
    detected_workbook_name = (
        request.sigma_workbook_name
        or vision.get("workbook_name")
        or workbook_label
    )

    # Narrate what we found
    if metrics:
        labels = [m.get("label", "") for m in metrics[:4]]
        high_conf = sum(1 for m in metric_mapping if m.get("confidence") == "high")
        med_conf = sum(1 for m in metric_mapping if m.get("confidence") == "medium")
        narration = (
            f"I can see **{len(metrics)} metrics** in **{detected_workbook_name}** ({domain} · {grain}): "
            + ", ".join(labels)
            + (f", and {len(metrics) - 4} more" if len(metrics) > 4 else "")
            + f". Schema mapping confidence — {high_conf} high, {med_conf} medium. "
            + "Building the dbt project and Sigma repointing guide now..."
        )
    else:
        narration = (
            f"Analyzing **{detected_workbook_name}** ({domain}) against {len(source_tables)} source tables. "
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

        # Write Sigma repointing guide into the zip
        guide_md = _generate_repointing_guide(
            vision=vision,
            mapping=mapping,
            connection_database=request.connection.database,
            workbook_name=detected_workbook_name,
        )
        guide_path = os.path.join(output_dir, "SIGMA_REPOINTING_GUIDE.md")
        Path(guide_path).write_text(guide_md, encoding="utf-8")

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

    # Summarise the repointing mapping for the chat message
    dataset_mappings = sigma_repointing.get("dataset_mapping", [])
    repoint_lines = ""
    if dataset_mappings:
        lines = [
            f"  • **{dm.get('current_sigma_dataset', '?')}** → `{dm.get('new_model', '?')}` ({dm.get('grain_change', '')})"
            for dm in dataset_mappings[:4]
        ]
        repoint_lines = "\n\n**Sigma repointing summary:**\n" + "\n".join(lines)
        if len(dataset_mappings) > 4:
            repoint_lines += f"\n  • _{len(dataset_mappings) - 4} more in SIGMA_REPOINTING_GUIDE.md_"

    emitter.emit(MessageEvent(
        run_id=run_id, delta=False,
        content=(
            f"Generated **{file_count} files** ({_human(len(zip_bytes))}) — "
            f"{len(staging_models)} staging models"
            + (f" and `{mart_name}`" if mart_models else "")
            + ". Includes `SIGMA_REPOINTING_GUIDE.md` with step-by-step instructions for switching your Sigma workbook to the new dbt-managed model."
            + repoint_lines
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


# ───────── Sigma repointing guide ─────────


def _generate_repointing_guide(
    vision: dict,
    mapping: dict,
    connection_database: str,
    workbook_name: str,
) -> str:
    """Produce SIGMA_REPOINTING_GUIDE.md from the LLM's repointing plan."""
    sigma_rp = mapping.get("sigma_repointing", {})
    new_conn = sigma_rp.get("new_connection", {})
    dataset_mappings = sigma_rp.get("dataset_mapping", [])
    column_renames = sigma_rp.get("column_renames", [])
    calcs_to_migrate = sigma_rp.get("calculated_fields_to_migrate", [])
    metrics = vision.get("metrics", [])
    mart_name = mapping.get("mart_name", f"mart_{connection_database.lower()}_summary")
    grain = mapping.get("grain", "unknown")
    domain = vision.get("domain", "Data")

    lines: list[str] = [
        f"# Sigma Repointing Guide — {workbook_name}",
        "",
        f"> Generated by DSA Platform · Dashboard Reverse-Engineering  ",
        f"> Domain: **{domain}** · Grain: **{grain}** · Target mart: `{mart_name}`",
        "",
        "---",
        "",
        "## 1. New Snowflake Connection",
        "",
        "After running `dbt run`, point your Sigma workbook at the dbt target schema:",
        "",
        "| Setting | Value |",
        "| ------- | ----- |",
        f"| Connection type | {new_conn.get('type', 'Snowflake')} |",
        f"| Database | `{new_conn.get('database', connection_database)}` |",
        f"| Schema | `{new_conn.get('schema', connection_database + '_dw')}` |",
        f"| Notes | {new_conn.get('note', 'dbt target schema — contains the mart views/tables')} |",
        "",
    ]

    # Dataset mapping table
    if dataset_mappings:
        lines += [
            "## 2. Dataset Mapping",
            "",
            "Replace each current Sigma dataset with the corresponding dbt model:",
            "",
            "| Current Sigma Dataset | New dbt Model | Model Type | Grain Change | Notes |",
            "| --------------------- | ------------- | ---------- | ------------ | ----- |",
        ]
        for dm in dataset_mappings:
            lines.append(
                f"| `{dm.get('current_sigma_dataset', '?')}` "
                f"| `{dm.get('new_model', '?')}` "
                f"| {dm.get('model_type', '?')} "
                f"| {dm.get('grain_change', '—')} "
                f"| {dm.get('notes', '—')} |"
            )
        lines.append("")
    else:
        lines += [
            "## 2. Dataset Mapping",
            "",
            f"Replace the current source datasets with `{mart_name}` in the dbt target schema.",
            "",
        ]

    # Column renames
    if column_renames:
        lines += [
            "## 3. Column Renames",
            "",
            "Update any Sigma formulas or column references that use the old names:",
            "",
            "| Old Column Name | New Column Name | Reason |",
            "| --------------- | --------------- | ------ |",
        ]
        for cr in column_renames:
            lines.append(
                f"| `{cr.get('current_name', '?')}` "
                f"| `{cr.get('new_name', '?')}` "
                f"| {cr.get('reason', '—')} |"
            )
        lines.append("")
    else:
        lines += [
            "## 3. Column Renames",
            "",
            "No column renames detected — existing column references should work unchanged.",
            "",
        ]

    # Calculated fields
    if calcs_to_migrate:
        lines += [
            "## 4. Calculated Fields",
            "",
            "| Sigma Formula | Description | Disposition |",
            "| ------------- | ----------- | ----------- |",
        ]
        for cf in calcs_to_migrate:
            disposition = cf.get("disposition", "keep_in_sigma")
            disposition_label = {
                "now_in_model": "✅ Pre-computed in mart — remove from Sigma",
                "simplifies_to_column": "✅ Now a plain column — replace formula with column ref",
                "keep_in_sigma": "➡️ Keep as Sigma calculation",
            }.get(disposition, disposition)
            lines.append(
                f"| `{cf.get('sigma_formula', '?')}` "
                f"| {cf.get('description', '—')} "
                f"| {disposition_label} |"
            )
        lines.append("")
    else:
        lines += [
            "## 4. Calculated Fields",
            "",
            "No Sigma calculations detected or all calculations are already in the mart model.",
            "",
        ]

    # Step-by-step Sigma UI instructions
    lines += [
        "## 5. Step-by-Step: Repointing in the Sigma UI",
        "",
        "1. Open the workbook in Sigma and click **Edit** (top-right).",
        "2. In the left panel, select **Data** → find your existing dataset(s) listed above.",
        "3. For each dataset, click the three-dot menu → **Replace connection/table**.",
        f"4. Select the new Snowflake connection pointing to schema `{new_conn.get('schema', connection_database + '_dw')}`.",
        "5. Choose the corresponding dbt mart model from the table list.",
        "6. If Sigma shows column-mapping warnings, use the Column Renames table above to resolve them.",
        "7. For any Sigma formulas marked **remove from Sigma** above, delete the calculated column.",
        "8. For formulas marked **replace formula with column ref**, swap the formula for the plain column name.",
        "9. Publish the workbook and verify all charts render correctly.",
        "",
    ]

    # Metrics validation checklist
    if metrics:
        lines += [
            "## 6. Validation Checklist",
            "",
            "After repointing, confirm each metric still renders with the expected values:",
            "",
        ]
        for m in metrics[:10]:
            lines.append(f"- [ ] **{m.get('label', '?')}** ({m.get('chart_type', '?')}) — {m.get('description', '')}")
        if len(metrics) > 10:
            lines.append(f"- [ ] _{len(metrics) - 10} additional metrics — verify each tab/page_")
        lines.append("")

    lines += [
        "---",
        "",
        "_This guide was generated automatically. Review with your Sigma admin before applying changes to production workbooks._",
    ]

    return "\n".join(lines)


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
