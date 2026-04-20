"""FastAPI dependencies: session-context extraction, JWT validation (stub).

Session-ID header contract: X-DSA-Session-ID per contracts/session-header.md.
JWT validation is a stub that returns ``cognito_sub=None`` in local mode; full
Cognito JWKS verification lands with T071 (US4).
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import Header, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field


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


async def get_session_context(
    request: Request,
    x_dsa_session_id: Annotated[str | None, Header(alias="X-DSA-Session-ID")] = None,
    authorization: Annotated[str | None, Header()] = None,
) -> SessionContext:
    """Extract a :class:`SessionContext` from request headers.

    - Missing or malformed ``X-DSA-Session-ID`` → 400.
    - In deployed mode, missing ``Authorization`` → 401.
    - JWT signature/issuer/audience verification is a stub that will land
      with T071; here we only parse the ``sub`` claim best-effort.
    """
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
        # Best-effort claim extraction until T071 wires real JWKS verification.
        # Do NOT trust these claims for authorization in deployed mode until T071.
        try:
            from jose import jwt  # type: ignore[import-untyped]

            token = authorization.removeprefix("Bearer ").strip()
            claims = jwt.get_unverified_claims(token)
            cognito_sub = claims.get("sub")
            username = claims.get("email") or claims.get("cognito:username")
        except Exception:
            if mode == "deployed":
                raise HTTPException(status_code=401, detail="Invalid JWT") from None
    elif mode == "deployed":
        raise HTTPException(status_code=401, detail="Authorization header required")

    return SessionContext(
        session_id=session_id,
        cognito_sub=cognito_sub,
        username=username,
        mode=mode,
    )


__all__ = ["SessionContext", "get_session_context"]
