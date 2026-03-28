"""On-demand evaluation for Platform Agent using AgentCore Evaluators.

Runs test cases against a deployed agent and evaluates responses with
built-in AgentCore evaluators: ToolSelectionAccuracy, Correctness,
GoalSuccessRate, Faithfulness.

Usage:
    uv run python eval/on_demand_eval.py [--agent-url URL] [--local]
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# Evaluators to run
EVALUATORS = [
    "Builtin.ToolSelectionAccuracy",
    "Builtin.Correctness",
    "Builtin.GoalSuccessRate",
    "Builtin.Faithfulness",
]


def load_test_cases() -> list[dict]:
    """Load test cases from eval/test_cases.json."""
    test_file = Path(__file__).parent / "test_cases.json"
    with open(test_file) as f:
        return json.load(f)


def run_agent_locally(prompt: str, agent_url: str) -> dict:
    """Send a prompt to the agent and return the response."""
    import urllib.request

    data = json.dumps({"prompt": prompt}).encode()
    req = urllib.request.Request(
        f"{agent_url}/invocations",
        data=data,
        headers={"Content-Type": "application/json"},
    )

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return {"status": "success", "response": resp.read().decode()}
    except Exception as e:
        return {"status": "error", "response": str(e)}


def check_expected_contains(response: str, expected: list[str]) -> dict:
    """Check if the response contains expected keywords."""
    response_lower = response.lower()
    results = {}
    for keyword in expected:
        results[keyword] = keyword.lower() in response_lower
    return results


def run_evaluation(agent_url: str) -> None:
    """Run all test cases and report results."""
    test_cases = load_test_cases()
    results = []

    logger.info("Running %d test cases against %s", len(test_cases), agent_url)

    for i, tc in enumerate(test_cases):
        logger.info("[%d/%d] %s: %s", i + 1, len(test_cases), tc["name"], tc["prompt"][:60])

        response = run_agent_locally(tc["prompt"], agent_url)

        # Basic keyword check
        contains = {}
        if response["status"] == "success" and "expected_contains" in tc:
            contains = check_expected_contains(
                response["response"], tc["expected_contains"]
            )

        passed = response["status"] == "success" and all(contains.values())
        results.append({
            "name": tc["name"],
            "status": response["status"],
            "contains_check": contains,
            "passed": passed,
        })

        status_icon = "PASS" if passed else "FAIL"
        logger.info("  %s — contains: %s", status_icon, contains)

    # Summary
    total = len(results)
    passed = sum(1 for r in results if r["passed"])
    failed = total - passed

    logger.info("")
    logger.info("=" * 50)
    logger.info("RESULTS: %d/%d passed, %d failed", passed, total, failed)
    logger.info("=" * 50)

    for r in results:
        icon = "PASS" if r["passed"] else "FAIL"
        logger.info("  %s  %s", icon, r["name"])

    # Try AgentCore evaluators if available
    try:
        _run_agentcore_evaluators(agent_url, test_cases)
    except ImportError:
        logger.info("")
        logger.info(
            "AgentCore starter toolkit not installed — skipping built-in evaluators."
        )
        logger.info("Install with: uv pip install bedrock-agentcore-starter-toolkit")
    except Exception:
        logger.exception("AgentCore evaluators failed")

    sys.exit(0 if failed == 0 else 1)


def _run_agentcore_evaluators(agent_url: str, test_cases: list[dict]) -> None:
    """Run AgentCore built-in evaluators (if toolkit is installed)."""
    from bedrock_agentcore_starter_toolkit import Evaluation

    logger.info("")
    logger.info("Running AgentCore built-in evaluators...")

    eval_client = Evaluation()

    for tc in test_cases:
        logger.info("  Evaluating: %s", tc["name"])
        try:
            results = eval_client.run(
                agent_id=os.environ.get("AGENT_ID", "platform-agent"),
                session_id=f"eval-{tc['name']}",
                evaluators=EVALUATORS,
            )
            for evaluator_name, score in results.items():
                logger.info("    %s: %s", evaluator_name, score)
        except Exception as e:
            logger.warning("    Evaluator failed: %s", e)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Platform Agent evaluation")
    parser.add_argument(
        "--agent-url",
        default=os.environ.get("AGENT_URL", "http://localhost:8080"),
        help="Agent endpoint URL (default: http://localhost:8080)",
    )
    args = parser.parse_args()
    run_evaluation(args.agent_url)


if __name__ == "__main__":
    main()
