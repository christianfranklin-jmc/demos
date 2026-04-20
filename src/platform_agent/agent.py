"""Strands Agent factory for the AWS Platform Agent.

Supports two shapes:

* Zero-arg / legacy call (``create_agent()``) — returns an agent with the full
  default tool set and the shared system prompt. Used by the CLI
  (``__main__.py``) and the legacy ``serve.py`` AG-UI adapter.
* Step-scoped call (``create_agent(step_id=StepId.REQUIREMENTS)``) — loads the
  step's dedicated system prompt from ``prompts/steps/`` and filters the tool
  set to the step's allowlist, per Constitution Article VI + ADR-015 D12.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from strands import Agent

from .models import DEFAULT_REGION, SONNET_MODEL_ID, create_model
from .prompts.system import SYSTEM_PROMPT
from .tools.dbt_generate import generate_dbt_project
from .tools.semantic_layer import generate_semantic_layer
from .tools.toolkit_connect import connect_to_database
from .tools.toolkit_ddl import execute_ddl
from .tools.toolkit_query import run_query
from .tools.toolkit_scan import profile_database, scan_metadata

if TYPE_CHECKING:
    from .workflow.steps import StepId

# Full default tool set — used in legacy / CLI / Streamlit paths.
DEFAULT_TOOLS = [
    connect_to_database,
    scan_metadata,
    profile_database,
    run_query,
    execute_ddl,
    generate_dbt_project,
    generate_semantic_layer,
]


def _filter_tools(allowed: frozenset[str]) -> list:
    """Return the subset of DEFAULT_TOOLS whose ``__name__`` is in ``allowed``.

    The registry's import-time validator guarantees every name resolves.
    """
    return [t for t in DEFAULT_TOOLS if getattr(t, "__name__", None) in allowed]


def create_agent(
    model_id: str = SONNET_MODEL_ID,
    region: str = DEFAULT_REGION,
    max_tokens: int = 8192,
    profile_name: str | None = None,
    tools: list | None = None,
    step_id: StepId | None = None,
) -> Agent:
    """Create and return a configured Platform Agent.

    Args:
        model_id: Bedrock model ID or inference profile ID.
        region: AWS region for the Bedrock service.
        max_tokens: Maximum tokens to generate per response.
        profile_name: AWS CLI profile name for authentication.
        tools: Explicit tool list override. Ignored if ``step_id`` is set.
        step_id: When provided, load the step-scoped prompt + tool allowlist from
            ``workflow.steps.STEP_REGISTRY``. Required for any FastAPI workflow
            path; optional for legacy consumers.
    """
    model = create_model(
        model_id=model_id,
        region=region,
        max_tokens=max_tokens,
        profile_name=profile_name,
    )

    if step_id is not None:
        from .workflow.steps import STEP_REGISTRY  # deferred to avoid circular import

        config = STEP_REGISTRY[step_id]
        system_prompt = config.system_prompt_path.read_text(encoding="utf-8")
        resolved_tools = _filter_tools(config.allowed_tools)
    else:
        system_prompt = SYSTEM_PROMPT
        resolved_tools = tools if tools is not None else DEFAULT_TOOLS

    return Agent(
        model=model,
        system_prompt=system_prompt,
        tools=resolved_tools,
    )
