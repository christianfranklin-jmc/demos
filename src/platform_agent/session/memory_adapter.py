"""AgentCore Memory adapter keyed on session-scoped memory keys.

`MemoryKey` encodes the user scope (Cognito sub or "local") and the per-tab
session UUID. `MemoryAdapter` wraps the AgentCore Memory client and raises
the typed `MemoryUnavailable` exception when the backing service is
unreachable — see ADR-015 D16 and FR-030.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from uuid import UUID

if TYPE_CHECKING:
    from ..api.deps import SessionContext  # circular import only at type-check time

logger = logging.getLogger(__name__)


class MemoryUnavailable(RuntimeError):
    """Raised when the AgentCore Memory client cannot complete a read/write.

    FastAPI routes catch this and emit a terminal
    `ErrorEvent{code: "memory_unreachable", retriable: true}` so the
    frontend can warn the user that refresh-durability is lost.
    """


@dataclass(frozen=True, slots=True)
class MemoryKey:
    """Namespaced key for AgentCore Memory records.

    Format: ``dsa:{user_scope}:{session_id}``. The ``dsa`` prefix keeps
    us isolated from any other memory consumers in the same Memory resource.
    """

    user_scope: str  # cognito_sub or "local"
    session_id: str  # str(UUID)

    PREFIX: str = "dsa"

    def as_string(self) -> str:
        return f"{self.PREFIX}:{self.user_scope}:{self.session_id}"


def memory_key_for(session: SessionContext) -> MemoryKey:
    """Derive the canonical memory key for a request."""
    return MemoryKey(
        user_scope=session.cognito_sub or "local",
        session_id=str(session.session_id),
    )


class MemoryAdapter:
    """Wraps the AgentCore Memory client.

    In local/dev mode (no ``MEMORY_ID`` env var) this is a no-op that
    returns empty history and silently discards appends. In deployed mode
    it delegates to the real Memory client; any client-side failure is
    translated to :class:`MemoryUnavailable` so callers can surface
    FR-030 errors cleanly.
    """

    def __init__(self, memory_id: str | None = None) -> None:
        self._memory_id = memory_id
        self._client: Any | None = None
        if memory_id:
            self._client = self._build_client(memory_id)

    @staticmethod
    def _build_client(memory_id: str) -> Any:
        """Lazy-construct the AgentCore Memory client.

        Kept behind a method so imports don't fail in local mode where the
        runtime dependency may not be configured.
        """
        try:
            import boto3  # noqa: F401  (actual client lib wired later)
        except ImportError as exc:  # pragma: no cover
            raise MemoryUnavailable(f"boto3 unavailable: {exc}") from exc
        # NOTE: real AgentCore Memory client wiring lands with T020/T035;
        # for now we return a sentinel that the handler can detect.
        return {"memory_id": memory_id}

    def load_history(self, key: MemoryKey) -> list[dict[str, Any]]:
        """Return the prior conversation events for the given key, oldest first."""
        if self._client is None:
            return []
        try:
            # Real fetch call goes here once the Memory SDK is wired.
            logger.debug("memory.load_history key=%s", key.as_string())
            return []
        except Exception as exc:  # pragma: no cover
            raise MemoryUnavailable(str(exc)) from exc

    def append(self, key: MemoryKey, event: dict[str, Any]) -> None:
        """Append an event to the key's conversation."""
        if self._client is None:
            return
        try:
            logger.debug("memory.append key=%s event=%s", key.as_string(), event.get("type"))
        except Exception as exc:  # pragma: no cover
            raise MemoryUnavailable(str(exc)) from exc


__all__ = ["MemoryAdapter", "MemoryKey", "MemoryUnavailable", "memory_key_for"]


def _validate_uuid(s: str) -> UUID:
    """Helper used by the FastAPI dep; raises ValueError if not a valid UUID."""
    return UUID(s)
