"""Authentication utilities for AgentCore patterns.

Provides JWT extraction and OAuth2 token management following
the FAST template patterns/utils/auth.py pattern.
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any

import boto3

logger = logging.getLogger(__name__)

# Cache for OAuth2 tokens
_token_cache: dict[str, Any] = {}


def extract_user_id_from_context(context: Any) -> str:
    """Extract user ID from pre-validated JWT token in the request context.

    Security: User identity comes from the JWT 'sub' claim, NOT from
    the request payload (which could be manipulated via prompt injection).
    The token is pre-validated by AgentCore Runtime.
    """
    try:
        token_claims = context.get("authorizer", {}).get("claims", {})
        user_id = token_claims.get("sub", "anonymous")
        return user_id
    except (AttributeError, KeyError):
        logger.warning("Could not extract user ID from context, using anonymous")
        return "anonymous"


def get_gateway_access_token() -> str:
    """Get OAuth2 access token for Gateway M2M authentication.

    Uses client_credentials grant via Cognito. Caches token until
    near expiration.
    """
    cache_key = "gateway_token"

    # Return cached token if still valid (with 60s buffer)
    if cache_key in _token_cache:
        cached = _token_cache[cache_key]
        if cached["expires_at"] > time.time() + 60:
            return cached["access_token"]

    # Retrieve machine client credentials from Secrets Manager
    region = os.environ.get("AWS_REGION", os.environ.get("AWS_DEFAULT_REGION", "us-east-1"))
    stack_name = os.environ.get("STACK_NAME", "platform-agent-stack")

    ssm = boto3.client("ssm", region_name=region)
    secrets = boto3.client("secretsmanager", region_name=region)

    # Get client ID from SSM
    client_id_param = ssm.get_parameter(
        Name=f"/{stack_name}/machine_client_id",
        WithDecryption=False,
    )
    client_id = client_id_param["Parameter"]["Value"]

    # Get client secret from Secrets Manager
    secret_response = secrets.get_secret_value(
        SecretId=f"{stack_name}/machine_client_secret",
    )
    client_secret = json.loads(secret_response["SecretString"])["client_secret"]

    # Get Cognito domain from SSM
    domain_param = ssm.get_parameter(
        Name=f"/{stack_name}/cognito_domain_url",
        WithDecryption=False,
    )
    token_url = f"{domain_param['Parameter']['Value']}/oauth2/token"

    # Request token via client_credentials grant
    import base64
    import urllib.parse
    import urllib.request

    auth_header = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    data = urllib.parse.urlencode({
        "grant_type": "client_credentials",
        "scope": f"{stack_name}-gateway/read {stack_name}-gateway/write",
    }).encode()

    req = urllib.request.Request(
        token_url,
        data=data,
        headers={
            "Authorization": f"Basic {auth_header}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )

    with urllib.request.urlopen(req) as resp:
        token_data = json.loads(resp.read().decode())

    _token_cache[cache_key] = {
        "access_token": token_data["access_token"],
        "expires_at": time.time() + token_data.get("expires_in", 3600),
    }

    return token_data["access_token"]
