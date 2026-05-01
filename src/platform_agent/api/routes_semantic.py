"""Semantic graph read routes (T106, US5).

GET /semantic/graph?connection_id=...&domain=...
GET /semantic/entities/{entity_id}?connection_id=...

Per Q2: each endpoint reads from one connection's ConnectionStore.
Cross-connection unification is explicitly out of scope (FR-022). v1
is read-only (FR-025); writes happen exclusively through the
provisioning flow's `semantic_agent`.
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from platform_agent.api.deps import SessionContext, get_session_context
from platform_agent.semantic.models import (
    Cardinality,
    Domain,
    Metric,
    PhysicalBinding,
    SemanticEntity,
)
from platform_agent.semantic.store import make_store
from platform_agent.workspace.registry import get_registry

logger = logging.getLogger(__name__)
router = APIRouter(tags=["semantic"])


# ───── Response shapes ─────


class GraphEntityRow(BaseModel):
    entity_id: str
    name: str
    domain: Domain
    metric_count: int
    binding_count: int
    version: int


class GraphJoinRow(BaseModel):
    join_id: str
    left_entity_id: str
    right_entity_id: str
    cardinality: Cardinality


class GraphKPIStrip(BaseModel):
    entities: int
    metrics: int
    joins: int
    bindings: int
    processes_mapped_pct: float = Field(ge=0.0, le=100.0)


class SemanticGraphResponse(BaseModel):
    connection_id: str
    entities: list[GraphEntityRow]
    joins: list[GraphJoinRow]
    kpi_strip: GraphKPIStrip


class EntityDetail(BaseModel):
    entity: SemanticEntity
    bindings: list[PhysicalBinding]
    metrics: list[Metric]


# ───── Endpoints ─────


@router.get("/semantic/graph", response_model=SemanticGraphResponse)
async def get_graph(
    ctx: Annotated[SessionContext, Depends(get_session_context)],
    connection_id: Annotated[str, Query(min_length=1)],
    domain: Annotated[str | None, Query()] = None,
) -> SemanticGraphResponse:
    # Sanity-check that the requesting workspace knows about this
    # connection. Strictly we could allow reads against any known
    # connection_id (the durable store is content-addressed), but
    # gating on workspace membership keeps tabs honest.
    ws = get_registry().get_or_create(ctx.session_id)
    known = {c.connection_id for c in ws.connections}
    if connection_id not in known:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "connection_not_in_workspace",
                "message": f"connection {connection_id} not in this workspace",
            },
        )

    store = make_store(connection_id)
    try:
        entities = store.list_entities(domain=domain)
        joins = store.list_joins()
        all_metrics = store.list_metrics()
        all_bindings = store.list_bindings()
    finally:
        store.close()

    metric_count_by_entity: dict[str, int] = {}
    for m in all_metrics:
        for eid in m.entity_ids:
            metric_count_by_entity[eid] = metric_count_by_entity.get(eid, 0) + 1
    binding_count_by_entity: dict[str, int] = {}
    for b in all_bindings:
        binding_count_by_entity[b.entity_id] = (
            binding_count_by_entity.get(b.entity_id, 0) + 1
        )

    rows = [
        GraphEntityRow(
            entity_id=e.entity_id,
            name=e.name,
            domain=e.domain,
            metric_count=metric_count_by_entity.get(e.entity_id, 0),
            binding_count=binding_count_by_entity.get(e.entity_id, 0),
            version=e.version,
        )
        for e in entities
    ]
    join_rows = [
        GraphJoinRow(
            join_id=j.join_id,
            left_entity_id=j.left_entity_id,
            right_entity_id=j.right_entity_id,
            cardinality=j.cardinality,
        )
        for j in joins
    ]
    return SemanticGraphResponse(
        connection_id=connection_id,
        entities=rows,
        joins=join_rows,
        kpi_strip=GraphKPIStrip(
            entities=len(rows),
            metrics=len(all_metrics),
            joins=len(join_rows),
            bindings=len(all_bindings),
            # Process-mapping ratio plugs in when discovery cache + entity
            # binding refs share a process indexer (Phase 9 / T127).
            processes_mapped_pct=0.0,
        ),
    )


@router.get("/semantic/entities/{entity_id}", response_model=EntityDetail)
async def get_entity_detail(
    entity_id: str,
    ctx: Annotated[SessionContext, Depends(get_session_context)],
    connection_id: Annotated[str, Query(min_length=1)],
) -> EntityDetail:
    ws = get_registry().get_or_create(ctx.session_id)
    if connection_id not in {c.connection_id for c in ws.connections}:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    store = make_store(connection_id)
    try:
        entity = store.get_entity(entity_id)
        if entity is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
        bindings = store.list_bindings(entity_id=entity_id)
        all_metrics = store.list_metrics()
    finally:
        store.close()
    metrics = [m for m in all_metrics if entity_id in m.entity_ids]
    return EntityDetail(entity=entity, bindings=bindings, metrics=metrics)


__all__ = ["router"]
