"""Semantic graph entity Pydantic models (data-model.md §4–§7).

All entities are scoped to a single connection in v1 (Q2). Cross-
connection links are intentionally unrepresentable in this module.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator


class Domain(StrEnum):
    WEALTH_MGMT = "wealth_mgmt"
    ACCOUNTING = "accounting"
    CRM = "crm"
    HR = "hr"
    PLANNING = "planning"
    UNSPECIFIED = "unspecified"


class Cardinality(StrEnum):
    ONE_TO_ONE = "one_to_one"
    ONE_TO_MANY = "one_to_many"
    MANY_TO_MANY = "many_to_many"


class Attribute(BaseModel):
    name: str
    data_type: str
    is_pii: bool = False  # informational only in v1 (Q4)
    description: str | None = None


class PhysicalBinding(BaseModel):
    binding_id: str
    entity_id: str
    connection_id: str
    fully_qualified_name: str  # `<scope>.<schema>.<table>`
    column_map: dict[str, str] = Field(default_factory=dict)
    row_count_estimate: int | None = None
    last_validated_at: datetime | None = None


class Metric(BaseModel):
    metric_id: str
    connection_id: str
    name: str
    definition_sql: str
    entity_ids: list[str] = Field(default_factory=list)
    unit: str | None = None
    created_by_run_id: str | None = None
    version: int = 1

    @field_validator("definition_sql")
    @classmethod
    def _read_only(cls, v: str) -> str:
        # Defense-in-depth: blocking write keywords at the model boundary.
        # Authoritative enforcement still happens in the query path.
        from platform_agent.workspace.read_only import assert_read_only

        assert_read_only(v)
        return v


class Join(BaseModel):
    join_id: str
    connection_id: str
    left_entity_id: str
    right_entity_id: str
    join_keys: list[tuple[str, str]] = Field(default_factory=list)
    cardinality: Cardinality


class SemanticEntity(BaseModel):
    entity_id: str
    connection_id: str
    name: str
    domain: Domain = Domain.UNSPECIFIED
    attributes: list[Attribute] = Field(default_factory=list)
    metric_ids: list[str] = Field(default_factory=list)
    physical_binding_ids: list[str] = Field(default_factory=list)
    created_by_run_id: str | None = None
    created_at: datetime
    updated_at: datetime
    version: int = 1

    @field_validator("physical_binding_ids")
    @classmethod
    def _at_least_one_binding(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("SemanticEntity requires ≥1 physical_binding_ids")
        return v
