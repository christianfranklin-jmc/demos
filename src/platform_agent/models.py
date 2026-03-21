"""Bedrock model configuration for the AWS Platform Agent."""

import boto3
from strands.models import BedrockModel

# US cross-region inference profiles for better throughput
SONNET_MODEL_ID = "us.anthropic.claude-sonnet-4-20250514-v1:0"
OPUS_MODEL_ID = "us.anthropic.claude-opus-4-20250514-v1:0"

DEFAULT_REGION = "us-east-1"
DEFAULT_MAX_TOKENS = 8192


def create_model(
    model_id: str = SONNET_MODEL_ID,
    region: str = DEFAULT_REGION,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    profile_name: str | None = None,
) -> BedrockModel:
    """Create a BedrockModel instance.

    Args:
        model_id: Bedrock model ID or inference profile ID.
        region: AWS region for the Bedrock service.
        max_tokens: Maximum tokens to generate per response.
        profile_name: AWS CLI profile name for authentication.
    """
    boto_session = boto3.Session(profile_name=profile_name, region_name=region)

    return BedrockModel(
        boto_session=boto_session,
        model_id=model_id,
        max_tokens=max_tokens,
    )
