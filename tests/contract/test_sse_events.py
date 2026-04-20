"""Contract tests for the SSE event schema v1.

Round-trips every Pydantic model through model_dump -> JSON -> model_validate
and asserts structural equality. Rejects malformed events (bad version,
invalid codes, unknown fields).

Relates to: contracts/sse-events.md, ADR-015 D14, and the frontend parser in
frontend/src/lib/agentcore-client/parsers/v1/.
"""

from __future__ import annotations

import json
from uuid import uuid4

import pytest
from pydantic import ValidationError

from platform_agent.api.events import (
    ArtifactReadyEvent,
    ArtifactUpdateEvent,
    ConceptualModelPayload,
    DoneEvent,
    Entity,
    ErrorEvent,
    HeartbeatEvent,
    LogicalField,
    LogicalModelPayload,
    LogicalTable,
    MessageEvent,
    PrdPayload,
    PrdSection,
    Relationship,
    ToolProgressEvent,
    ToolResultEvent,
    ToolStartEvent,
    event_name,
    is_terminal,
)


def _roundtrip(model):
    """Encode → JSON-ish dict → decode → equality."""
    payload = json.loads(model.model_dump_json())
    restored = type(model).model_validate(payload)
    assert restored == model


def test_heartbeat_roundtrip():
    _roundtrip(HeartbeatEvent())
    assert event_name(HeartbeatEvent()) == "heartbeat"


def test_tool_start_roundtrip():
    event = ToolStartEvent(run_id=uuid4(), tool="scan_metadata", args_summary="schema=public")
    _roundtrip(event)
    assert event_name(event) == "tool_start"


def test_tool_progress_bounds():
    # note capped at 100 chars
    with pytest.raises(ValidationError):
        ToolProgressEvent(
            run_id=uuid4(),
            tool="scan_metadata",
            note="x" * 101,
        )
    ok = ToolProgressEvent(
        run_id=uuid4(),
        tool="scan_metadata",
        note="x" * 100,
        index=4,
        total=14,
    )
    _roundtrip(ok)


def test_tool_result_roundtrip():
    event = ToolResultEvent(run_id=uuid4(), tool="scan_metadata", summary="Found 14 tables.")
    _roundtrip(event)


def test_message_delta_default():
    event = MessageEvent(run_id=uuid4(), content="Hi", delta=True)
    assert event.role == "assistant"
    _roundtrip(event)


def test_artifact_update_prd():
    payload = PrdPayload(
        sections=[
            PrdSection(
                heading="Problem",
                body="Grounded.",
                cited_tables=["public.orders"],
                completeness_contribution=0.5,
            )
        ],
        completeness=0.5,
    )
    event = ArtifactUpdateEvent(
        run_id=uuid4(),
        step="requirements",
        artifact_type="prd",
        payload=payload,
    )
    _roundtrip(event)


def test_artifact_update_conceptual():
    event = ArtifactUpdateEvent(
        run_id=uuid4(),
        step="conceptual",
        artifact_type="conceptual_model",
        payload=ConceptualModelPayload(
            entities=[
                Entity(id="o", label="Orders", source_table="public.orders", key_columns=["id"])
            ],
            relationships=[
                Relationship(
                    from_entity_id="o",
                    to_entity_id="c",
                    from_column="customer_id",
                    to_column="id",
                    cardinality="N:1",
                )
            ],
        ),
    )
    _roundtrip(event)


def test_artifact_update_logical():
    event = ArtifactUpdateEvent(
        run_id=uuid4(),
        step="logical",
        artifact_type="logical_model",
        payload=LogicalModelPayload(
            tables=[
                LogicalTable(
                    id="fct_orders",
                    label="Orders Fact",
                    grain="one row per order",
                    fields=[
                        LogicalField(
                            name="order_id",
                            data_type="integer",
                            nullable=False,
                            sample_values=["1", "2", "3"],
                            role="id",
                        )
                    ],
                )
            ]
        ),
    )
    _roundtrip(event)


def test_artifact_ready_roundtrip_and_terminal():
    event = ArtifactReadyEvent(
        run_id=uuid4(),
        handle=uuid4(),
        size_bytes=1024,
        file_count=5,
        expires_in_s=60,
        download_url="/workflow/artifact/abc",
    )
    _roundtrip(event)
    assert is_terminal(event)


def test_error_roundtrip_and_terminal():
    for code in (
        "tool_error",
        "agent_error",
        "cancelled",
        "timeout",
        "unauthorized",
        "validation_error",
        "memory_unreachable",
    ):
        event = ErrorEvent(code=code, message="x", retriable=False)  # type: ignore[arg-type]
        _roundtrip(event)
        assert is_terminal(event)


def test_error_rejects_unknown_code():
    with pytest.raises(ValidationError):
        ErrorEvent(code="bogus", message="x", retriable=False)  # type: ignore[arg-type]


def test_done_roundtrip_and_terminal():
    event = DoneEvent(run_id=uuid4(), step="requirements")
    _roundtrip(event)
    assert is_terminal(event)


def test_extra_fields_rejected():
    """Every event model forbids extra — regression guard against schema drift."""
    with pytest.raises(ValidationError):
        HeartbeatEvent.model_validate({"v": 1, "t": "2026-04-20T00:00:00Z", "bogus": True})


def test_logical_field_rejects_bad_role():
    with pytest.raises(ValidationError):
        LogicalField(
            name="x",
            data_type="text",
            nullable=True,
            role="unknown",  # type: ignore[arg-type]
        )


def test_relationship_rejects_bad_cardinality():
    with pytest.raises(ValidationError):
        Relationship(
            from_entity_id="a",
            to_entity_id="b",
            from_column="x",
            to_column="y",
            cardinality="many",  # type: ignore[arg-type]
        )
