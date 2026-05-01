"""delivery_agent — auto-validation + product promotion (T075, US3 / R8).

The terminal agent. Runs each PRD business question through the
cross-source TTYD planner (stubbed in v1 — real planner lands in US4),
records ValidationResult per question, computes the pass rate, and
flips the registered Iceberg product from `provisional` to `final` iff
pass rate ≥ DSA_HUB_VALIDATION_THRESHOLD (default 0.80, Q5).

v1 stub uses a deterministic pass/fail policy (every other question
passes) so tests can exercise both the success-promotion path and the
needs-replan path. The LLM-as-judge swap is a single-function change
in `_simulate_validation()`.
"""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime

from platform_agent.provisioning.agents._base import (
    AgentContext,
    AgentOutput,
)
from platform_agent.provisioning.models import (
    AgentId,
    Artifact,
    IcebergDataProduct,
    ProductState,
    ValidationResult,
    ValidationState,
)
from platform_agent.semantic.store import make_store
from platform_agent.workspace.activity_log import write as log_activity
from platform_agent.workspace.activity_models import ActivityKind


def _threshold() -> float:
    raw = os.environ.get("DSA_HUB_VALIDATION_THRESHOLD", "0.80")
    try:
        return float(raw)
    except ValueError:
        return 0.80


def run(ctx: AgentContext) -> AgentOutput:
    questions = list(ctx.prd.business_questions)
    threshold = _threshold()
    ctx.emit_progress(
        f"running auto-validation: {len(questions)} question(s), threshold={threshold:.2f}"
    )

    artifacts: list[Artifact] = []
    results: list[ValidationResult] = []
    fqn = ctx.prd.target.fqn()

    for i, q in enumerate(questions, 1):
        ctx.emit_progress(f"validating question {i}/{len(questions)}")
        result = _simulate_validation(ctx, q, i)
        results.append(result)
        artifacts.append(
            Artifact(
                kind="validation_result",
                ref=result.result_id,
                meta=result.model_dump(mode="json"),
            )
        )
        ctx.emit_artifact(artifacts[-1])

    passed = sum(1 for r in results if r.state == ValidationState.PASSED)
    pass_rate = passed / len(results) if results else 0.0
    is_final = pass_rate >= threshold

    # Find the IcebergDataProduct the mapping_agent registered.
    mapping_artifacts = ctx.upstream_artifacts.get(AgentId.MAPPING, [])
    product_artifact = next(
        (a for a in mapping_artifacts if a.kind == "iceberg_data_product"), None
    )
    if product_artifact is None:
        return AgentOutput(
            artifacts=artifacts,
            error={
                "code": "missing_product",
                "message": "mapping_agent did not register an iceberg_data_product",
                "retryable": True,
            },
        )

    # Promote (or leave provisional) and persist to the target connection's store.
    raw = dict(product_artifact.meta)
    raw["state"] = ProductState.FINAL.value if is_final else ProductState.PROVISIONAL.value
    raw["ttyd_exposed"] = is_final
    raw["validation_pass_rate"] = pass_rate
    raw["validation_results"] = [r.model_dump(mode="json") for r in results]
    raw["updated_at"] = datetime.now(tz=UTC).isoformat()
    product = IcebergDataProduct.model_validate(raw)

    store = make_store(ctx.prd.target.connection_id)
    store.upsert_product(product)
    store.close()

    log_activity(
        connection_id=ctx.prd.target.connection_id,
        workspace_id=uuid.UUID(ctx.workspace_id),
        kind=ActivityKind.PRODUCT_REGISTERED if not is_final else ActivityKind.PRODUCT_PROMOTED,
        payload={
            "product_id": product.product_id,
            "table": fqn,
            "state": product.state.value,
            "pass_rate": pass_rate,
        },
    )

    final_artifact = Artifact(
        kind="iceberg_data_product",
        ref=product.product_id,
        meta=product.model_dump(mode="json"),
    )
    artifacts.append(final_artifact)
    ctx.emit_artifact(final_artifact)
    return AgentOutput(artifacts=artifacts)


def _simulate_validation(
    ctx: AgentContext, question: str, index: int
) -> ValidationResult:
    """v1 stub: deterministic pass/fail policy.

    Override-friendly: tests can monkeypatch this for full-pass / full-fail
    scenarios. The LLM-as-judge swap (R8) is a single-function replacement.
    """
    # Default policy: every odd question (1st, 3rd, ...) passes; even ones
    # alternate based on the threshold so tests can hit both branches.
    passed = index % 2 == 1 or index % 4 == 0
    return ValidationResult(
        result_id=str(uuid.uuid4()),
        run_id=ctx.run_id,
        question=question,
        state=ValidationState.PASSED if passed else ValidationState.FAILED,
        sql_executed=f"SELECT * FROM {ctx.prd.target.fqn()} WHERE 1=1 LIMIT 5",
        result_preview=[{"sample_row": "redacted"}] if passed else None,
        latency_ms=42,
        judge_reasoning=(
            "result matches expected range (stub)"
            if passed
            else "result outside expected range (stub)"
        ),
        evaluated_at=datetime.now(tz=UTC),
    )
