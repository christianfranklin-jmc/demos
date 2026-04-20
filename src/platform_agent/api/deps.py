"""FastAPI dependencies: session-context extraction + Cognito JWT validation.

Session-ID header contract: X-DSA-Session-ID per contracts/session-header.md.
In deployed mode we verify the JWT against the Cognito User Pool's JWKS
(fetched once on first request and cached for the life of the process).

Configuration (resolved in this order):
  1. Environment: ``COGNITO_USER_POOL_ID`` / ``COGNITO_APP_CLIENT_ID``
  2. SSM: ``/<STACK_NAME>/cognito/user_pool_id`` and ``…/app_client_id``

If neither source is populated, deployed-mode requests 401 with a helpful
message ("Cognito not configured"). Local mode never touches Cognito.
"""

from __future__ import annotations

import logging
import os
from datetime import UTC, datetime
from functools import lru_cache
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import Header, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)


class SessionContext(BaseModel):
    """Per-request session identity, built from the X-DSA-Session-ID header + JWT."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    session_id: UUID
    cognito_sub: str | None = None
    username: str | None = None
    mode: Literal["local", "deployed"]
    issued_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))


def _current_mode() -> Literal["local", "deployed"]:
    return "deployed" if os.environ.get("AGENT_MODE") == "deployed" else "local"


@lru_cache(maxsize=1)
def _cognito_config() -> tuple[str, str, str] | None:
    """Return (region, user_pool_id, app_client_id) or None when unconfigured.

    Tries env vars first, then SSM parameters under ``/<STACK_NAME>/cognito/*``.
    Cached for the life of the process.
    """
    region = os.environ.get("AWS_REGION", os.environ.get("AWS_DEFAULT_REGION", "us-east-1"))
    user_pool_id = os.environ.get("COGNITO_USER_POOL_ID")
    app_client_id = os.environ.get("COGNITO_APP_CLIENT_ID")

    if not user_pool_id or not app_client_id:
        stack_name = os.environ.get("STACK_NAME")
        if stack_name:
            try:
                import boto3  # lazy — only imported when SSM lookup is attempted

                client = boto3.client("ssm", region_name=region)
                if not user_pool_id:
                    user_pool_id = client.get_parameter(
                        Name=f"/{stack_name}/cognito/user_pool_id"
                    )["Parameter"]["Value"]
                if not app_client_id:
                    app_client_id = client.get_parameter(
                        Name=f"/{stack_name}/cognito/app_client_id"
                    )["Parameter"]["Value"]
            except Exception as exc:  # noqa: BLE001 — any failure → fall back to "unconfigured"
                logger.warning("SSM Cognito lookup failed: %s", exc)

    if not user_pool_id or not app_client_id:
        return None
    return region, user_pool_id, app_client_id


@lru_cache(maxsize=1)
def _jwks() -> dict[str, Any] | None:
    """Fetch the Cognito User Pool JWKS. Cached for the life of the process.

    Cognito rotates JWKS rarely; if we ever need to rotate in-flight we can
    bust this cache with a targeted ``_jwks.cache_clear()`` call.
    """
    cfg = _cognito_config()
    if cfg is None:
        return None
    region, user_pool_id, _ = cfg
    url = f"https://cognito-idp.{region}.amazonaws.com/{user_pool_id}/.well-known/jwks.json"
    try:
        from urllib.request import urlopen

        with urlopen(url, timeout=5) as response:  # noqa: S310 — trusted AWS URL
            import json as _json

            return _json.loads(response.read())  # type: ignore[no-any-return]
    except Exception as exc:  # noqa: BLE001
        logger.warning("JWKS fetch failed from %s: %s", url, exc)
        return None


def _verify_jwt(token: str) -> dict[str, Any]:
    """Verify signature + issuer + audience against Cognito. Returns claims."""
    cfg = _cognito_config()
    jwks = _jwks()
    if cfg is None or jwks is None:
        raise HTTPException(status_code=401, detail="Cognito not configured")

    region, user_pool_id, app_client_id = cfg
    issuer = f"https://cognito-idp.{region}.amazonaws.com/{user_pool_id}"

    try:
        from jose import jwt  # type: ignore[import-untyped]
    except ImportError as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail="python-jose missing") from exc

    try:
        claims = jwt.decode(
            token,
            jwks,
            algorithms=["RS256"],
            audience=app_client_id,
            issuer=issuer,
            options={"verify_at_hash": False},
        )
    except Exception as exc:  # noqa: BLE001 — wrap every jose error as 401
        raise HTTPException(status_code=401, detail=f"Invalid JWT: {exc}") from None
    return claims  # type: ignore[no-any-return]


async def get_session_context(
    request: Request,
    x_dsa_session_id: Annotated[str | None, Header(alias="X-DSA-Session-ID")] = None,
    authorization: Annotated[str | None, Header()] = None,
) -> SessionContext:
    """Extract a :class:`SessionContext` from request headers.

    - Missing or malformed ``X-DSA-Session-ID`` → 400.
    - In deployed mode, missing ``Authorization`` → 401.
    - In deployed mode, JWT is verified against Cognito JWKS. In local mode,
      if an Authorization header is present we best-effort parse its claims
      without signature verification (useful for dev-server Cognito mocks).
    """
    _ = request  # reserved for future rate-limit hooks
    if not x_dsa_session_id:
        raise HTTPException(status_code=400, detail="Missing X-DSA-Session-ID header")
    try:
        session_id = UUID(x_dsa_session_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=400, detail="X-DSA-Session-ID is not a valid UUID"
        ) from exc

    mode = _current_mode()
    cognito_sub: str | None = None
    username: str | None = None

    if authorization:
        token = authorization.removeprefix("Bearer ").strip()
        if mode == "deployed":
            claims = _verify_jwt(token)
            cognito_sub = claims.get("sub")
            username = claims.get("email") or claims.get("cognito:username")
        else:
            # Local-mode best-effort parse. NOT security-relevant — local-mode
            # routes ignore the sub anyway (memory key prefix "local").
            try:
                from jose import jwt  # type: ignore[import-untyped]

                claims = jwt.get_unverified_claims(token)
                cognito_sub = claims.get("sub")
                username = claims.get("email") or claims.get("cognito:username")
            except Exception:  # noqa: BLE001
                pass
    elif mode == "deployed":
        raise HTTPException(status_code=401, detail="Authorization header required")

    return SessionContext(
        session_id=session_id,
        cognito_sub=cognito_sub,
        username=username,
        mode=mode,
    )


__all__ = ["SessionContext", "get_session_context"]
