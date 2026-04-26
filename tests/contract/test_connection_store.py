"""Contract tests for ConnectionStore (T024).

Exercises the Protocol against the local SQLite backend. The DynamoDB
backend uses the same Protocol; a deployed-mode contract test against
moto/local-stack lives separately under `tests/integration/`.
"""

from __future__ import annotations

import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest


# Use a per-test temp dir so we never touch ~/.dsa-hub
@pytest.fixture(autouse=True)
def _tmp_connections_dir(monkeypatch: pytest.MonkeyPatch) -> None:
    tmp = tempfile.mkdtemp(prefix="dsa-hub-test-")
    monkeypatch.setenv("DSA_HUB_CONNECTIONS_DIR", tmp)
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    yield
    # tempfile cleans up at exit; we don't need to manually remove


@pytest.fixture
def store():
    from platform_agent.semantic.store import make_store

    cid = "test-" + uuid.uuid4().hex[:12]
    s = make_store(cid)
    yield s
    s.close()


def _entity(cid: str, name: str = "client", *, eid: str = "e1") -> object:
    from platform_agent.semantic.models import Attribute, Domain, SemanticEntity

    now = datetime.now(tz=UTC)
    return SemanticEntity(
        entity_id=eid,
        connection_id=cid,
        name=name,
        domain=Domain.CRM,
        attributes=[Attribute(name="client_id", data_type="int")],
        physical_binding_ids=["b1"],
        created_at=now,
        updated_at=now,
    )


def test_factory_returns_sqlite_in_local_mode(store):
    from platform_agent.semantic.store_local import SQLiteConnectionStore

    assert isinstance(store, SQLiteConnectionStore)


def test_entity_upsert_and_round_trip(store):
    e = _entity(store.connection_id)
    store.upsert_entity(e)
    fetched = store.get_entity("e1")
    assert fetched is not None
    assert fetched.name == "client"
    assert fetched.connection_id == store.connection_id


def test_entity_cross_connection_assignment_rejected(store):
    e = _entity(cid="some-other-connection-id")
    with pytest.raises(ValueError, match="does not match"):
        store.upsert_entity(e)


def test_metric_round_trip(store):
    from platform_agent.semantic.models import Metric

    m = Metric(
        metric_id="m1",
        connection_id=store.connection_id,
        name="client_count",
        definition_sql="SELECT COUNT(*) FROM clients",
        entity_ids=["e1"],
    )
    store.upsert_metric(m)
    metrics = store.list_metrics()
    assert [m.name for m in metrics] == ["client_count"]


def test_metric_blocks_write_sql(store):
    from pydantic import ValidationError

    from platform_agent.semantic.models import Metric

    # Pydantic v2 wraps field_validator exceptions in ValidationError; the
    # underlying ReadOnlyViolation is still in the cause chain.
    with pytest.raises(ValidationError, match="read_only_violation"):
        Metric(
            metric_id="m1",
            connection_id=store.connection_id,
            name="bad",
            definition_sql="DELETE FROM clients",
            entity_ids=["e1"],
        )


def test_activity_log_append_only(store):
    from platform_agent.workspace.activity_models import ActivityKind, ActivityLogEntry

    ws = uuid.uuid4()
    for i in range(3):
        store.append_activity(
            ActivityLogEntry(
                entry_id=f"a{i}",
                connection_id=store.connection_id,
                workspace_id=ws,
                kind=ActivityKind.PRD_DRAFTED,
                payload={"i": i},
                ts=datetime.now(tz=UTC),
            )
        )
    entries = store.list_activity()
    assert len(entries) == 3
    # newest first
    assert [int(e.payload["i"]) for e in entries] == [2, 1, 0]


def test_product_invariant_final_must_be_exposed(store):
    from platform_agent.provisioning.models import IcebergDataProduct, ProductState
    from platform_agent.workflow.pill_models import IcebergTarget, PRDDraft

    prd = PRDDraft(
        prd_id="prd-1",
        title="Client 360",
        target=IcebergTarget(
            connection_id=store.connection_id,
            glue_db="dsa_hub_pinnacle_360",
            table_name="fct_client_360",
        ),
        business_questions=["What is Q1 advisor productivity?"],
        standards_applied=["naming.conventions.kimball"],
    )
    now = datetime.now(tz=UTC)
    bad = IcebergDataProduct(
        product_id="p1",
        connection_id=store.connection_id,
        table_name="iceberg.dsa_hub_pinnacle_360.fct_client_360",
        state=ProductState.FINAL,
        ttyd_exposed=False,  # invariant violation
        created_by_run_id="r1",
        prd_snapshot=prd,
        validation_pass_rate=1.0,
        created_at=now,
        updated_at=now,
    )
    with pytest.raises(ValueError, match="Invariant violation"):
        store.upsert_product(bad)


def test_discovery_cache_round_trip(store):
    store.write_discovery_cache({"tables": 14, "processes": 8})
    assert store.read_discovery_cache() == {"tables": 14, "processes": 8}


def test_persistence_across_reopen(store, tmp_path: Path):
    from platform_agent.semantic.store import make_store

    e = _entity(store.connection_id)
    store.upsert_entity(e)
    cid = store.connection_id
    store.close()

    reopened = make_store(cid)
    fetched = reopened.get_entity("e1")
    assert fetched is not None and fetched.name == "client"
    reopened.close()
