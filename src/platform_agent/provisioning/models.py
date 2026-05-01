"""Provisioning + validation + product Pydantic models (data-model.md §12-§15).

Covers RedundancyReport (gate input), ProvisioningRun + AgentExecution
(orchestrator state), IcebergDataProduct (terminal artifact, final or
provisional per Q5), ValidationResult (auto-validation rows).
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from platform_agent.workflow.pill_models import PRDDraft

# ───── Redundancy gate ─────


class OverlapKind(StrEnum):
    ENTITY = "entity"
    METRIC = "metric"


class RedundancyState(StrEnum):
    NET_NEW = "net_new"
    PARTIAL_OVERLAP = "partial_overlap"
    DUPLICATE = "duplicate"


class OverlapItem(BaseModel):
    proposed_name: str
    existing_id: str
    kind: OverlapKind
    overlap_pct: float = Field(..., ge=0.0, le=100.0)
    side_by_side_diff: str = ""


class DecisionKind(StrEnum):
    REUSE = "reuse"
    OVERRIDE = "override"


class Decision(BaseModel):
    overlap_existing_id: str
    kind: DecisionKind
    rationale: str = ""


class RedundancyReport(BaseModel):
    report_id: str
    prd_id: str
    target_connection_id: str
    state: RedundancyState
    overlaps: list[OverlapItem] = Field(default_factory=list)
    decisions: list[Decision] = Field(default_factory=list)
    override_rationale: str | None = None
    generated_at: datetime
    cleared_to_provision: bool = False


# ───── Provisioning run / agent execution ─────


class AgentId(StrEnum):
    SCHEMA = "schema"
    PIPELINE = "pipeline"
    MODEL = "model"
    QUALITY = "quality"
    MAPPING = "mapping"
    SEMANTIC = "semantic"
    DELIVERY = "delivery"


class AgentState(StrEnum):
    PENDING = "pending"
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"


class RunState(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    NEEDS_REPLAN = "needs_replan"
    FAILED = "failed"


class AgentError(BaseModel):
    code: str
    message: str
    retryable: bool = True


class Artifact(BaseModel):
    kind: str
    ref: str
    meta: dict[str, Any] = Field(default_factory=dict)


class AgentExecution(BaseModel):
    agent_id: AgentId
    state: AgentState = AgentState.PENDING
    attempt: int = 1
    started_at: datetime | None = None
    completed_at: datetime | None = None
    artifacts: list[Artifact] = Field(default_factory=list)
    error: AgentError | None = None
    latency_ms_p95: int | None = None


class KpiTick(BaseModel):
    ts: datetime
    rows_in_motion: int = 0
    agents_active: int = 0
    files_written: int = 0
    latency_ms_p95: int | None = None
    est_cost_usd: float | None = None
    eta_seconds: int | None = None


class ProvisioningRun(BaseModel):
    run_id: str
    workspace_id: UUID
    prd_id: str
    target_connection_id: str
    state: RunState = RunState.QUEUED
    agents: list[AgentExecution] = Field(default_factory=list)
    kpi_series: list[KpiTick] = Field(default_factory=list)
    validation_pass_rate: float | None = None
    final_product_id: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


# ───── Iceberg Data Product (terminal artifact) ─────


class ProductState(StrEnum):
    PROVISIONAL = "provisional"
    FINAL = "final"


class IcebergDataProduct(BaseModel):
    product_id: str
    connection_id: str
    table_name: str
    state: ProductState = ProductState.PROVISIONAL
    ttyd_exposed: bool = False
    created_by_run_id: str
    prd_snapshot: PRDDraft
    validation_pass_rate: float = 0.0
    validation_results: list[ValidationResult] = Field(default_factory=list)
    entity_ids_introduced: list[str] = Field(default_factory=list)
    metric_ids_introduced: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


# ───── Auto-validation per-question result ─────


class ValidationState(StrEnum):
    PENDING = "pending"
    PASSED = "passed"
    FAILED = "failed"


class ValidationResult(BaseModel):
    result_id: str
    run_id: str
    question: str
    state: ValidationState = ValidationState.PENDING
    sql_executed: str | None = None
    result_preview: list[dict[str, Any]] | None = None
    latency_ms: int | None = None
    judge_reasoning: str | None = None
    evaluated_at: datetime | None = None


# Pydantic forward-ref resolution
IcebergDataProduct.model_rebuild()
