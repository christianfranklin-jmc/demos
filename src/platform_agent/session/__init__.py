"""Session identity + AgentCore Memory adapter.

Session scope is defined in docs/adr/015-dsa-agent-integration.md D6, D11.
The memory key is derived from Cognito sub (or "local") + per-tab session UUID.
"""

from .memory_adapter import MemoryAdapter, MemoryKey, MemoryUnavailable

__all__ = ["MemoryAdapter", "MemoryKey", "MemoryUnavailable"]
