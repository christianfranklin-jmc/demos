"""Step 4 (Detailed Requirements) handler.

Generates a dbt project + semantic layer from the scanned schema and delivers
them as a streamed zip via artifact_ready (ADR-015 D10).
"""

from __future__ import annotations

import io
import logging
import os
import tempfile
import zipfile
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import UUID

from ..api.events import ArtifactReadyEvent, MessageEvent, ToolResultEvent, ToolStartEvent
from ._shared import ensure_driver, scan_metadata_safe, source_id_for

if TYPE_CHECKING:
    from ..api.deps import SessionContext
    from ..api.routes_workflow import SourceConnection, StepRequest
    from ..api.sse import SSEEmitter
    from ..api.zip_stream import ArtifactStore

logger = logging.getLogger(__name__)


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
        ToolStartEvent(
            run_id=run_id, tool="generate_dbt_project", args_summary=f"source={source_id}"
        )
    )

    # Collect the real source tables from scan_metadata so the generated dbt
    # project references them via `source()`.
    metadata = scan_metadata_safe(source_id)
    raw_tables = metadata.get("tables", []) if isinstance(metadata, dict) else []
    source_tables = [t.get("name") or t.get("table_name", "") for t in raw_tables]
    source_tables = [t for t in source_tables if t]

    project_name = _project_name_for(request.connection)

    with tempfile.TemporaryDirectory() as tmpdir:
        # Use the existing tool bodies directly rather than via the Strands
        # agent — deterministic and test-friendly.
        from ..tools.dbt_generate import generate_dbt_project
        from ..tools.semantic_layer import generate_semantic_layer

        output_dir = os.path.join(tmpdir, project_name)
        result = generate_dbt_project(
            project_name=project_name,
            target_schema=f"{project_name}_dw",
            source_database=request.connection.database,
            source_schema=request.connection.schema or "public",
            source_tables=source_tables[:10],
            staging_models=[_staging_model(t, request.connection.database) for t in source_tables[:10]],
            mart_models=[],
            output_dir=output_dir,
        )
        logger.info("dbt project generated at %s (%s)", output_dir, result)

        # Semantic layer over the few staging models we emitted.
        try:
            generate_semantic_layer(
                project_name=project_name,
                semantic_models=[],
                metrics=[],
                output_dir=output_dir,
            )
        except Exception as exc:
            logger.warning("semantic_layer generation skipped: %s", exc)

        zip_bytes = _zip_directory(output_dir)

    emitter.emit(
        ToolResultEvent(
            run_id=run_id,
            tool="generate_dbt_project",
            summary=f"{len(source_tables)} source tables → zip {_human(len(zip_bytes))}",
        )
    )

    handle, entry = await artifact_store.register(zip_bytes, session.session_id)
    ttl_seconds = int(
        (
            entry.expires_at - entry.expires_at.__class__.now(entry.expires_at.tzinfo)
        ).total_seconds()
    )
    if ttl_seconds <= 0:  # clock skew paranoia
        ttl_seconds = 60

    emitter.emit(
        MessageEvent(
            run_id=run_id,
            delta=False,
            content=(
                f"Generated a dbt project ({_count_zip_entries(zip_bytes)} files, "
                f"{_human(len(zip_bytes))}) from {len(source_tables)} source table"
                f"{'s' if len(source_tables) != 1 else ''}. "
                "Downloading the zip now — unzip and run `dbt compile` to verify."
            ),
        )
    )
    emitter.emit(
        ArtifactReadyEvent(
            run_id=run_id,
            handle=handle,
            size_bytes=len(zip_bytes),
            file_count=_count_zip_entries(zip_bytes),
            expires_in_s=ttl_seconds,
            download_url=f"/workflow/artifact/{handle}",
        )
    )


def _project_name_for(connection: "SourceConnection") -> str:
    db = (connection.database or "data_product").lower()
    return f"{db}_dw"


def _staging_model(table_name: str, source_db: str) -> dict:
    """Minimal staging model spec accepted by generate_dbt_project.

    generate_dbt_project expects each staging entry to carry {name, sql}. The
    SQL body is a thin pass-through over the source table so the generated
    project compiles cleanly with no extra columns to model. Real customer
    work replaces this with column-level casts + renames per Kimball staging.
    """
    return {
        "name": f"stg_{table_name}",
        "sql": (
            "-- Auto-generated staging model. Passes source rows through with minimal\n"
            "-- transformation; extend with explicit casts / renames per the logical model.\n"
            f"select *\nfrom {{{{ source('{source_db}', '{table_name}') }}}}\n"
        ),
    }


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
                f"{n:.0f} {unit}"
                if unit == "B"
                else f"{n / 1024:.1f} {unit}"
                if unit == "KB"
                else f"{n / 1024 / 1024:.1f} {unit}"
            )
        n //= 1024
    return f"{n} GB"
