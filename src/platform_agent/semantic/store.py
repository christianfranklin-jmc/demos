"""ConnectionStore Protocol + factory (research.md R2).

Each connection owns its own durable store, keyed by ``connection_id``.
``STORAGE_BACKEND`` env selects the implementation:

- ``local`` (default) → SQLite at ``~/.dsa-hub/connections/<id>/store.db``
- ``dynamodb``        → single-table ``DSAHubConnectionStore`` partition
                        on ``connection_id``

Per Q2, no entity in any store references entities in any *other*
connection's store; cross-connection joins are not representable here.
"""

from __future__ import annotations

import os
from typing import Any, Protocol, runtime_checkable

from platform_agent.provisioning.models import IcebergDataProduct
from platform_agent.semantic.models import (
    Join,
    Metric,
    PhysicalBinding,
    SemanticEntity,
)
from platform_agent.workspace.activity_models import ActivityLogEntry


@runtime_checkable
class ConnectionStore(Protocol):
    """Per-connection durable storage interface."""

    connection_id: str

    # ───── Semantic graph ─────
    def upsert_entity(self, entity: SemanticEntity) -> None: ...
    def get_entity(self, entity_id: str) -> SemanticEntity | None: ...
    def list_entities(self, *, domain: str | None = None) -> list[SemanticEntity]: ...

    def upsert_binding(self, binding: PhysicalBinding) -> None: ...
    def list_bindings(self, *, entity_id: str | None = None) -> list[PhysicalBinding]: ...

    def upsert_metric(self, metric: Metric) -> None: ...
    def list_metrics(self) -> list[Metric]: ...

    def upsert_join(self, join: Join) -> None: ...
    def list_joins(self) -> list[Join]: ...

    # ───── Iceberg products (only meaningful on iceberg-driver connections) ─────
    def upsert_product(self, product: IcebergDataProduct) -> None: ...
    def get_product(self, product_id: str) -> IcebergDataProduct | None: ...
    def list_products(self) -> list[IcebergDataProduct]: ...

    # ───── Activity log (append-only) ─────
    def append_activity(self, entry: ActivityLogEntry) -> None: ...
    def list_activity(self, *, limit: int = 200) -> list[ActivityLogEntry]: ...

    # ───── Discovery cache ─────
    def write_discovery_cache(self, payload: dict[str, Any]) -> None: ...
    def read_discovery_cache(self) -> dict[str, Any] | None: ...

    def close(self) -> None: ...


def _backend_from_env() -> str:
    return os.environ.get("STORAGE_BACKEND", "local").strip().lower()


def make_store(connection_id: str) -> ConnectionStore:
    """Construct a store for the given ``connection_id`` based on env."""
    backend = _backend_from_env()
    if backend == "dynamodb":
        from platform_agent.semantic.store_deployed import DynamoDBConnectionStore

        return DynamoDBConnectionStore(connection_id=connection_id)
    if backend in {"", "local"}:
        from platform_agent.semantic.store_local import SQLiteConnectionStore

        return SQLiteConnectionStore(connection_id=connection_id)
    raise ValueError(f"Unsupported STORAGE_BACKEND={backend!r}; expected 'local' or 'dynamodb'")
