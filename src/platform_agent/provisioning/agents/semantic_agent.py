"""semantic_agent — writes new entities + metrics into the target connection's
graph (T074, US3).

The semantic agent runs after mapping has registered the Iceberg table.
It walks the PRD's proposed entities/metrics/joins and persists them
into the **target Connection's** ConnectionStore (Q2 — never cross-
connection). v1 implementation is pure-Python deterministic; an Opus 4.7
LLM-driven reconciliation pass lands when ADR-019 D-LLM is amended.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from platform_agent.provisioning.agents._base import (
    AgentContext,
    AgentOutput,
)
from platform_agent.provisioning.models import Artifact
from platform_agent.semantic.models import (
    Attribute,
    Domain,
    Metric,
    PhysicalBinding,
    SemanticEntity,
)
from platform_agent.semantic.store import make_store


def run(ctx: AgentContext) -> AgentOutput:
    target_cid = ctx.prd.target.connection_id
    ctx.emit_progress(
        f"writing entities + metrics into connection store {target_cid[:12]}…"
    )

    store = make_store(target_cid)
    artifacts: list[Artifact] = []
    now = datetime.now(tz=UTC)

    entity_ids: list[str] = []
    for proposed_entity in ctx.prd.entities_proposed:
        entity_id = str(uuid4())
        binding_id = str(uuid4())
        binding = PhysicalBinding(
            binding_id=binding_id,
            entity_id=entity_id,
            connection_id=target_cid,
            fully_qualified_name=ctx.prd.target.fqn(),
            column_map={a.name: a.name for a in proposed_entity.attributes},
        )
        entity = SemanticEntity(
            entity_id=entity_id,
            connection_id=target_cid,
            name=proposed_entity.name,
            domain=Domain.UNSPECIFIED,
            attributes=[
                Attribute(
                    name=a.name,
                    data_type=a.data_type,
                    is_pii=a.is_pii,
                )
                for a in proposed_entity.attributes
            ],
            metric_ids=[],
            physical_binding_ids=[binding_id],
            created_by_run_id=ctx.run_id,
            created_at=now,
            updated_at=now,
        )
        # Entity must be inserted first — physical_bindings has a FK
        # to entities(entity_id) (see semantic/migrations/__init__.py).
        store.upsert_entity(entity)
        store.upsert_binding(binding)
        entity_ids.append(entity_id)
        artifacts.append(
            Artifact(
                kind="semantic_entity",
                ref=entity_id,
                meta={
                    "name": proposed_entity.name,
                    "binding": binding.fully_qualified_name,
                },
            )
        )
        ctx.emit_artifact(artifacts[-1])

    metric_ids: list[str] = []
    for proposed_metric in ctx.prd.metrics_proposed:
        metric_id = str(uuid4())
        metric = Metric(
            metric_id=metric_id,
            connection_id=target_cid,
            name=proposed_metric.name,
            definition_sql=proposed_metric.definition_sql,
            entity_ids=entity_ids,
            unit=proposed_metric.unit,
            created_by_run_id=ctx.run_id,
        )
        store.upsert_metric(metric)
        metric_ids.append(metric_id)
        artifacts.append(
            Artifact(
                kind="semantic_metric",
                ref=metric_id,
                meta={"name": proposed_metric.name, "unit": proposed_metric.unit},
            )
        )
        ctx.emit_artifact(artifacts[-1])

    summary = Artifact(
        kind="semantic_graph_diff",
        ref=f"{target_cid}#diff",
        meta={
            "entities_added": len(entity_ids),
            "metrics_added": len(metric_ids),
        },
    )
    artifacts.append(summary)
    ctx.emit_artifact(summary)

    store.close()
    return AgentOutput(artifacts=artifacts)
