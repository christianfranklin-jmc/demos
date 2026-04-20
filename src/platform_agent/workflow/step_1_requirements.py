"""Step 1 (Requirements / PRD) handler.

Stub — body lands in T036. Signature is stable now so the router in
T035 can import and dispatch without waiting for the implementation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..api.deps import SessionContext
    from ..api.sse import SSEEmitter
    from .requests import StepRequest  # to be created in T035


async def run(
    request: "StepRequest",
    session: "SessionContext",
    emitter: "SSEEmitter",
) -> None:
    """Run Step 1 against the connected database.

    Produces `artifact_update.prd` events grounded in `scan_metadata` output,
    then emits `done` on gate-worthy completion.
    """
    raise NotImplementedError("T036 lands the Step 1 body")
