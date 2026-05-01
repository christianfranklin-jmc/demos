"""DynamoDB-backed ConnectionStore — deployed mode.

Single-table ``DSAHubConnectionStore`` with PK ``connection_id`` and
SK ``entity_kind#entity_id``. Sparse GSI on ``(connection_id, kind)``
for kind-scoped queries.

Boto3 is imported lazily so the local-mode runtime never pays the
import cost. The Terraform definition lives in
``infra-terraform/modules/data/main.tf`` (see T023; deferred from
the local-only Phase 2 scope).
"""

from __future__ import annotations

import os
from typing import Any
from uuid import UUID

from platform_agent.provisioning.models import IcebergDataProduct
from platform_agent.semantic.models import (
    Join,
    Metric,
    PhysicalBinding,
    SemanticEntity,
)
from platform_agent.workspace.activity_models import ActivityKind, ActivityLogEntry

_TABLE_NAME = os.environ.get("DSA_HUB_DDB_TABLE", "DSAHubConnectionStore")


class DynamoDBConnectionStore:
    """Single-table DynamoDB implementation of the ConnectionStore Protocol."""

    def __init__(self, *, connection_id: str, table_name: str | None = None) -> None:
        import boto3  # lazy

        self.connection_id = connection_id
        self._table = boto3.resource("dynamodb").Table(table_name or _TABLE_NAME)

    def _key(self, kind: str, ident: str) -> dict[str, str]:
        return {"connection_id": self.connection_id, "sk": f"{kind}#{ident}"}

    def _put(self, kind: str, ident: str, payload: dict[str, Any]) -> None:
        item = {**self._key(kind, ident), "kind": kind, "payload": payload}
        self._table.put_item(Item=item)

    def _get(self, kind: str, ident: str) -> dict[str, Any] | None:
        resp = self._table.get_item(Key=self._key(kind, ident))
        item = resp.get("Item")
        return item["payload"] if item else None

    def _list(self, kind: str) -> list[dict[str, Any]]:
        from boto3.dynamodb.conditions import Key

        resp = self._table.query(
            KeyConditionExpression=Key("connection_id").eq(self.connection_id)
            & Key("sk").begins_with(f"{kind}#")
        )
        return [item["payload"] for item in resp.get("Items", [])]

    # ───── Semantic graph ─────

    def upsert_entity(self, entity: SemanticEntity) -> None:
        self._put("entity", entity.entity_id, entity.model_dump(mode="json"))

    def get_entity(self, entity_id: str) -> SemanticEntity | None:
        payload = self._get("entity", entity_id)
        return SemanticEntity.model_validate(payload) if payload else None

    def list_entities(self, *, domain: str | None = None) -> list[SemanticEntity]:
        items = self._list("entity")
        entities = [SemanticEntity.model_validate(item) for item in items]
        if domain is not None:
            entities = [e for e in entities if e.domain.value == domain]
        return entities

    def upsert_binding(self, binding: PhysicalBinding) -> None:
        self._put("binding", binding.binding_id, binding.model_dump(mode="json"))

    def list_bindings(self, *, entity_id: str | None = None) -> list[PhysicalBinding]:
        items = [PhysicalBinding.model_validate(item) for item in self._list("binding")]
        if entity_id is not None:
            items = [b for b in items if b.entity_id == entity_id]
        return items

    def upsert_metric(self, metric: Metric) -> None:
        self._put("metric", metric.metric_id, metric.model_dump(mode="json"))

    def list_metrics(self) -> list[Metric]:
        return [Metric.model_validate(item) for item in self._list("metric")]

    def upsert_join(self, join: Join) -> None:
        self._put("join", join.join_id, join.model_dump(mode="json"))

    def list_joins(self) -> list[Join]:
        return [Join.model_validate(item) for item in self._list("join")]

    # ───── Iceberg products ─────

    def upsert_product(self, product: IcebergDataProduct) -> None:
        self._put("product", product.product_id, product.model_dump(mode="json"))

    def get_product(self, product_id: str) -> IcebergDataProduct | None:
        payload = self._get("product", product_id)
        return IcebergDataProduct.model_validate(payload) if payload else None

    def list_products(self) -> list[IcebergDataProduct]:
        return [IcebergDataProduct.model_validate(item) for item in self._list("product")]

    # ───── Activity log ─────

    def append_activity(self, entry: ActivityLogEntry) -> None:
        # Use the entry_id as the SK; activity is read by query+sort, not by ID.
        self._put("activity", entry.entry_id, entry.model_dump(mode="json"))

    def list_activity(self, *, limit: int = 200) -> list[ActivityLogEntry]:
        items = self._list("activity")
        out: list[ActivityLogEntry] = []
        for item in items:
            # DynamoDB JSON loses UUID/enum types; reconstruct.
            item["workspace_id"] = UUID(item["workspace_id"])
            item["kind"] = ActivityKind(item["kind"])
            out.append(ActivityLogEntry.model_validate(item))
        out.sort(key=lambda e: e.ts, reverse=True)
        return out[:limit]

    # ───── Discovery cache ─────

    def write_discovery_cache(self, payload: dict[str, Any]) -> None:
        self._put("discovery_cache", "current", payload)

    def read_discovery_cache(self) -> dict[str, Any] | None:
        return self._get("discovery_cache", "current")

    def close(self) -> None:
        # boto3 sessions don't require explicit close; method preserved for the Protocol.
        return None
