"""SSM Parameter Store utilities for AgentCore patterns.

Following FAST template patterns/utils/ssm.py pattern.
"""

from __future__ import annotations

import os

import boto3


def get_ssm_parameter(name: str, with_decryption: bool = False) -> str:
    """Retrieve a parameter value from AWS Systems Manager Parameter Store.

    Args:
        name: Full parameter name (e.g., '/platform-agent-stack/gateway_url').
        with_decryption: Whether to decrypt SecureString parameters.

    Returns:
        The parameter value string.

    Raises:
        ValueError: If the parameter is not found.
    """
    region = os.environ.get("AWS_REGION", os.environ.get("AWS_DEFAULT_REGION", "us-east-1"))
    client = boto3.client("ssm", region_name=region)

    try:
        response = client.get_parameter(Name=name, WithDecryption=with_decryption)
        return response["Parameter"]["Value"]
    except client.exceptions.ParameterNotFound as err:
        raise ValueError(f"SSM parameter not found: {name}") from err
