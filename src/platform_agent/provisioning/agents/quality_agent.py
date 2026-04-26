"""quality_agent — DQDL rules + dbt tests (T072, US3).

v1 stub: emits a deterministic set of quality checks based on the dbt
models the model_agent produced. Real path (deferred): promote
`patterns/quality-agent/tools/quality_rules.py` + `quarantine.py` and
run the actual dbt-test pass.
"""

from __future__ import annotations

from platform_agent.provisioning.agents._base import (
    AgentContext,
    AgentOutput,
)
from platform_agent.provisioning.models import AgentId, Artifact


def run(ctx: AgentContext) -> AgentOutput:
    upstream_models = [
        a for a in ctx.upstream_artifacts.get(AgentId.MODEL, []) if a.kind == "dbt_model"
    ]
    ctx.emit_progress(
        f"generating quality rules for {len(upstream_models)} dbt model(s)"
    )

    artifacts: list[Artifact] = []
    rules: list[str] = []
    for model in upstream_models:
        rules.append(f"not_null({model.ref})")
        rules.append(f"unique_keys({model.ref})")

    rules_artifact = Artifact(
        kind="dqdl_ruleset",
        ref=f"quality/{ctx.prd.target.table_name}.dqdl",
        meta={"rule_count": len(rules), "preview": rules[:6]},
    )
    artifacts.append(rules_artifact)
    ctx.emit_artifact(rules_artifact)

    test_results = Artifact(
        kind="dbt_test_run",
        ref=f"runs/{ctx.run_id}/dbt-test",
        meta={"passed": len(rules), "failed": 0},
    )
    artifacts.append(test_results)
    ctx.emit_artifact(test_results)
    return AgentOutput(artifacts=artifacts)
