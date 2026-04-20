"""Step 3 (Logical Model) handler.

Stub — body lands in T038.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..api.deps import SessionContext
    from ..api.sse import SSEEmitter
    from .requests import StepRequest


async def run(
    request: "StepRequest",
    session: "SessionContext",
    emitter: "SSEEmitter",
) -> None:
    """Run Step 3 — populate logical fields with real data types + top-5 samples."""
    raise NotImplementedError("T038 lands the Step 3 body")
