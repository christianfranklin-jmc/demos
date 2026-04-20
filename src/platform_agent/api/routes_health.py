"""Liveness probe — no auth, no session requirement.

Used by Docker healthcheck, AgentCore Runtime readiness, and frontend "Local" /
"Deployed" indicator (Constitution Article V "backend mode MUST be visible").
"""

from __future__ import annotations

import os
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    build: str
    mode: Literal["local", "deployed"]


router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(
        build=os.environ.get("BUILD_SHA", "dev"),
        mode="deployed" if os.environ.get("AGENT_MODE") == "deployed" else "local",
    )
