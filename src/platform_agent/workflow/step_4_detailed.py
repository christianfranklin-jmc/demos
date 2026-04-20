"""Step 4 (Detailed Requirements — dbt zip) handler.

Stub — body lands in T039. Terminates with `artifact_ready` (no `done`).
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
    """Run Step 4 — generate dbt project + semantic YAML, package, issue handle."""
    raise NotImplementedError("T039 lands the Step 4 body")
