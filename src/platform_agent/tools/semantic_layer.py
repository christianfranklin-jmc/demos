"""Tool: Generate dbt Semantic Layer YAML (MetricFlow) for a star schema."""

from __future__ import annotations

import os
from uuid import uuid4

import yaml
from strands import tool


def _emit_progress(note: str, index: int | None = None, total: int | None = None) -> None:
    try:
        from ..api.events import ToolProgressEvent
        from ..api.sse import heartbeat_emitter
    except ImportError:
        return
    emitter = heartbeat_emitter.get()
    if emitter is None:
        return
    emitter(
        ToolProgressEvent(
            run_id=uuid4(),
            tool="generate_semantic_layer",
            note=note,
            index=index,
            total=total,
        )
    )


@tool
def generate_semantic_layer(
    project_name: str,
    semantic_models: list[dict],
    metrics: list[dict],
    output_dir: str = "",
) -> dict:
    """Generate a dbt Semantic Layer YAML file for MetricFlow from a star schema.

    Call this after a dimensional model and dbt project have been created to add
    semantic definitions (entities, dimensions, measures) and metrics that can be
    queried through the dbt Semantic Layer API.

    Args:
        project_name: Name of the dbt project (e.g., "northwinds_dw").
        semantic_models: List of semantic model definitions. Each dict has:
            - name: Model name matching a dbt model (e.g., "fct_order_lines")
            - description: What the model represents
            - entities: List of dicts with keys:
                - name: Entity name (e.g., "order_line")
                - type: "primary" or "foreign"
                - expr: Column expression (e.g., "order_line_key")
            - dimensions: List of dicts with keys:
                - name: Dimension name (e.g., "order_date")
                - type: "categorical" or "time"
                - expr: Column expression
                - type_params: (optional) Dict for time dimensions (e.g., {"time_granularity": "day"})
            - measures: List of dicts with keys:
                - name: Measure name (e.g., "total_revenue")
                - agg: Aggregation type — "sum", "count", "avg", "min", "max", or "count_distinct"
                - expr: Column expression
                - description: (optional) What the measure calculates
        metrics: List of metric definitions. Each dict has:
            - name: Metric name (e.g., "total_revenue")
            - description: What the metric measures
            - type: "simple", "derived", or "ratio"
            - type_params: Dict whose keys depend on type:
                - simple: {"measure": "<measure_name>"}
                - derived: {"expr": "<expression>", "metrics": [{"name": "<metric_name>", "offset_window": ...}, ...]}
                - ratio: {"numerator": {"name": "<metric>"}, "denominator": {"name": "<metric>"}}
        output_dir: Directory to write into. Defaults to "dbt_output/<project_name>".
    """
    _emit_progress(
        f"generating semantic layer for {project_name}",
        total=len(semantic_models) + len(metrics),
    )

    base_dir = output_dir or os.path.join(os.getcwd(), "dbt_output", project_name)
    marts_dir = os.path.join(base_dir, "models", "marts")
    os.makedirs(marts_dir, exist_ok=True)

    # Build semantic_models section
    sm_entries = []
    for sm in semantic_models:
        # Determine default agg_time_dimension from first time dimension
        agg_time_dim = None
        for dim in sm.get("dimensions", []):
            if dim.get("type") == "time":
                agg_time_dim = dim["name"]
                break

        entry: dict = {
            "name": sm["name"],
            "model": f"ref('{sm['name']}')",
            "description": sm.get("description", ""),
        }

        if agg_time_dim:
            entry["defaults"] = {"agg_time_dimension": agg_time_dim}

        # Entities
        entities = []
        for e in sm.get("entities", []):
            entity: dict = {"name": e["name"], "type": e["type"]}
            if "expr" in e:
                entity["expr"] = e["expr"]
            entities.append(entity)
        if entities:
            entry["entities"] = entities

        # Dimensions
        dimensions = []
        for d in sm.get("dimensions", []):
            dim: dict = {"name": d["name"], "type": d["type"]}
            if "expr" in d:
                dim["expr"] = d["expr"]
            if "type_params" in d:
                dim["type_params"] = d["type_params"]
            dimensions.append(dim)
        if dimensions:
            entry["dimensions"] = dimensions

        # Measures
        measures = []
        for m in sm.get("measures", []):
            measure: dict = {"name": m["name"], "agg": m["agg"]}
            if "expr" in m:
                measure["expr"] = m["expr"]
            if "description" in m:
                measure["description"] = m["description"]
            measures.append(measure)
        if measures:
            entry["measures"] = measures

        sm_entries.append(entry)

    # Build metrics section
    metric_entries = []
    for met in metrics:
        metric: dict = {
            "name": met["name"],
            "description": met.get("description", ""),
            "type": met["type"],
            "type_params": met.get("type_params", {}),
        }
        metric_entries.append(metric)

    # Assemble full document
    doc: dict = {}
    if sm_entries:
        doc["semantic_models"] = sm_entries
    if metric_entries:
        doc["metrics"] = metric_entries

    # Write YAML — use a custom representer so ref() is unquoted
    class _RefStr(str):
        """Marker for dbt ref() expressions that should not be quoted."""

    def _ref_representer(dumper: yaml.Dumper, data: _RefStr) -> yaml.ScalarNode:
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="")

    yaml.add_representer(_RefStr, _ref_representer)

    # Tag ref() values
    for entry in doc.get("semantic_models", []):
        if "model" in entry:
            entry["model"] = _RefStr(entry["model"])

    yaml_content = yaml.dump(doc, default_flow_style=False, sort_keys=False, width=120)

    file_path = os.path.join(marts_dir, "semantic.yml")
    with open(file_path, "w") as f:
        f.write(yaml_content)

    return {
        "status": "success",
        "file_path": file_path,
        "semantic_models_count": len(sm_entries),
        "metrics_count": len(metric_entries),
    }
