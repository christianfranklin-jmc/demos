"""Step registry: persona-scoped system prompts and tool allowlists per DSA step.

Enforces Constitution Article VI "Agent personas are step-scoped" — no
cross-step context bleed, no tool leakage. The module-level assertion at
import time verifies every allowlisted tool is actually registered on the
agent factory; a typo here is a hard import failure.
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


class StepId(StrEnum):
    REQUIREMENTS = "requirements"
    CONCEPTUAL = "conceptual"
    LOGICAL = "logical"
    DETAILED = "detailed"


class StepOutputContract(BaseModel):
    """Which SSE artifact events a step is expected to emit (used by contract tests)."""

    model_config = ConfigDict(extra="forbid")

    artifact_types: frozenset[str]
    requires_artifact_ready: bool = False


class StepConfig(BaseModel):
    """Per-step configuration loaded by the agent factory."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    step_id: StepId
    display_order: Annotated[int, Field(ge=1, le=4)]
    system_prompt_path: Path
    allowed_tools: frozenset[str]
    require_db_connection: bool
    output_contract: StepOutputContract


_PROMPTS_DIR = Path(__file__).parent.parent / "prompts" / "steps"


STEP_REGISTRY: dict[StepId, StepConfig] = {
    StepId.REQUIREMENTS: StepConfig(
        step_id=StepId.REQUIREMENTS,
        display_order=1,
        system_prompt_path=_PROMPTS_DIR / "step_1_requirements.md",
        allowed_tools=frozenset({"connect_to_database", "scan_metadata"}),
        require_db_connection=True,
        output_contract=StepOutputContract(artifact_types=frozenset({"prd"})),
    ),
    StepId.CONCEPTUAL: StepConfig(
        step_id=StepId.CONCEPTUAL,
        display_order=2,
        system_prompt_path=_PROMPTS_DIR / "step_2_conceptual.md",
        allowed_tools=frozenset({"scan_metadata", "run_query"}),
        require_db_connection=True,
        output_contract=StepOutputContract(artifact_types=frozenset({"conceptual_model"})),
    ),
    StepId.LOGICAL: StepConfig(
        step_id=StepId.LOGICAL,
        display_order=3,
        system_prompt_path=_PROMPTS_DIR / "step_3_logical.md",
        allowed_tools=frozenset({"run_query", "profile_database"}),
        require_db_connection=True,
        output_contract=StepOutputContract(artifact_types=frozenset({"logical_model"})),
    ),
    StepId.DETAILED: StepConfig(
        step_id=StepId.DETAILED,
        display_order=4,
        system_prompt_path=_PROMPTS_DIR / "step_4_detailed.md",
        allowed_tools=frozenset({"generate_dbt_project", "generate_semantic_layer"}),
        require_db_connection=True,
        output_contract=StepOutputContract(
            artifact_types=frozenset(), requires_artifact_ready=True
        ),
    ),
}


def _registered_tool_names() -> frozenset[str]:
    """Inspect the agent factory's DEFAULT_TOOLS to get canonical tool names."""
    from ..agent import DEFAULT_TOOLS  # local import avoids circular init

    names: set[str] = set()
    for tool in DEFAULT_TOOLS:
        name = getattr(tool, "__name__", None) or getattr(tool, "name", None)
        if name:
            names.add(name)
    return frozenset(names)


def _validate_registry() -> None:
    """Fail at import time if any step references a tool the factory does not export."""
    registered = _registered_tool_names()
    for step_id, config in STEP_REGISTRY.items():
        missing = config.allowed_tools - registered
        if missing:
            raise RuntimeError(
                f"Step {step_id.value} references unregistered tool(s): "
                f"{sorted(missing)}. Registered: {sorted(registered)}"
            )


_validate_registry()
