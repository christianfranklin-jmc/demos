"""Pill + PRD draft Pydantic models (data-model.md §10, §11).

PillSuggestions are the schema-grounded cross-source product chips
shown on Step 1; clicking one produces a PRDDraft pre-populated with
target / joins / business questions.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, field_validator

from platform_agent.semantic.models import Cardinality
from platform_agent.workspace.read_only import assert_read_only


class ProposedAttribute(BaseModel):
    name: str
    data_type: str
    is_pii: bool = False


class ProposedEntity(BaseModel):
    name: str
    attributes: list[ProposedAttribute] = Field(default_factory=list)


class ProposedMetric(BaseModel):
    name: str
    definition_sql: str
    unit: str | None = None

    @field_validator("definition_sql")
    @classmethod
    def _read_only(cls, v: str) -> str:
        assert_read_only(v)
        return v


class ProposedJoin(BaseModel):
    left_fqn: str
    right_fqn: str
    keys: list[tuple[str, str]] = Field(default_factory=list)
    cardinality: Cardinality


class SourcePullSpec(BaseModel):
    connection_id: str
    sql: str
    max_rows: int = 250

    @field_validator("max_rows")
    @classmethod
    def _cap(cls, v: int) -> int:
        if v < 1 or v > 250:
            raise ValueError("max_rows must be in [1, 250] (FR-018 per-source cap)")
        return v

    @field_validator("sql")
    @classmethod
    def _read_only(cls, v: str) -> str:
        assert_read_only(v)
        return v


class IcebergTarget(BaseModel):
    connection_id: str
    glue_db: str
    table_name: str

    def fqn(self) -> str:
        return f"iceberg.{self.glue_db}.{self.table_name}"


class PRDOrigin(str, Enum):
    PILL = "pill"
    MANUAL = "manual"


class PRDDraft(BaseModel):
    prd_id: str | None = None
    title: str
    target: IcebergTarget
    entities_proposed: list[ProposedEntity] = Field(default_factory=list)
    metrics_proposed: list[ProposedMetric] = Field(default_factory=list)
    joins_identified: list[ProposedJoin] = Field(default_factory=list)
    business_questions: list[str] = Field(default_factory=list)
    source_pulls: list[SourcePullSpec] = Field(default_factory=list)
    standards_applied: list[str] = Field(default_factory=list)
    origin: PRDOrigin = PRDOrigin.MANUAL

    @field_validator("business_questions")
    @classmethod
    def _at_least_one_question(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("PRDDraft requires ≥1 business_questions")
        return v

    @field_validator("standards_applied")
    @classmethod
    def _at_least_one_standard(cls, v: list[str]) -> list[str]:
        # SC-011: every generated PRD ends with a non-empty footer.
        if not v:
            raise ValueError("PRDDraft requires non-empty standards_applied (SC-011)")
        return v


class PillFlags(BaseModel):
    demo: bool = False  # FR-041 — canned demo-mode pills


class PillSuggestion(BaseModel):
    pill_id: str
    title: str
    subtitle: str = ""
    icon: str = "sparkles"
    target_iceberg_table: str
    source_connection_ids: list[str] = Field(default_factory=list)
    estimated_build_minutes: int = 5
    seed_prd_body: PRDDraft
    generated_at: datetime
    flags: PillFlags = Field(default_factory=PillFlags)

    @field_validator("target_iceberg_table")
    @classmethod
    def _three_segment_fqn(cls, v: str) -> str:
        parts = v.split(".")
        if len(parts) != 3 or parts[0] != "iceberg":
            raise ValueError(
                "target_iceberg_table must match `iceberg.<glue_db>.<table>`"
            )
        return v

    @field_validator("source_connection_ids")
    @classmethod
    def _at_least_one_source(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("PillSuggestion requires ≥1 source_connection_ids")
        return v
