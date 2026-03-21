"""Strands Agent factory for the AWS Platform Agent."""

from strands import Agent

from .models import DEFAULT_REGION, SONNET_MODEL_ID, create_model
from .prompts.system import SYSTEM_PROMPT


def create_agent(
    model_id: str = SONNET_MODEL_ID,
    region: str = DEFAULT_REGION,
    max_tokens: int = 8192,
    profile_name: str | None = None,
    tools: list | None = None,
) -> Agent:
    """Create and return a configured Platform Agent.

    Args:
        model_id: Bedrock model ID or inference profile ID.
        region: AWS region for the Bedrock service.
        max_tokens: Maximum tokens to generate per response.
        profile_name: AWS CLI profile name for authentication.
        tools: List of @tool functions to register. Empty list for no tools.
    """
    model = create_model(
        model_id=model_id,
        region=region,
        max_tokens=max_tokens,
        profile_name=profile_name,
    )

    return Agent(
        model=model,
        system_prompt=SYSTEM_PROMPT,
        tools=tools or [],
    )
