"""Step 2 (Conceptual Model) handler.

Stub — body lands in T037.
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
    """Run Step 2 — derive entities + relationships from the FK graph.

    Snowflake fallback: naming-heuristic inference with `inferred=True`.
    """
    raise NotImplementedError("T037 lands the Step 2 body")
