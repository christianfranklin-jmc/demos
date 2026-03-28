"""Configure online evaluation for production Platform Agent.

Sets up 10% sampling with GoalSuccessRate, ToolSelectionAccuracy,
and Faithfulness evaluators. Results appear in CloudWatch metrics.

Usage:
    uv run python eval/online_eval_config.py [--agent-id ID]
"""

from __future__ import annotations

import argparse
import logging
import os

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

ONLINE_EVALUATORS = [
    "Builtin.GoalSuccessRate",
    "Builtin.ToolSelectionAccuracy",
    "Builtin.Faithfulness",
]


def configure_online_evaluation(agent_id: str) -> None:
    """Create or update online evaluation configuration."""
    try:
        from bedrock_agentcore_starter_toolkit import Evaluation
    except ImportError:
        logger.error(
            "bedrock-agentcore-starter-toolkit not installed. "
            "Install with: uv pip install bedrock-agentcore-starter-toolkit"
        )
        return

    eval_client = Evaluation()

    config_name = f"{agent_id}-online-eval"
    logger.info("Configuring online evaluation: %s", config_name)
    logger.info("  Agent ID: %s", agent_id)
    logger.info("  Sampling rate: 10%%")
    logger.info("  Evaluators: %s", ONLINE_EVALUATORS)

    try:
        eval_client.create_online_config(
            config_name=config_name,
            agent_id=agent_id,
            sampling_rate=10.0,
            evaluator_list=ONLINE_EVALUATORS,
            enable_on_create=True,
        )
        logger.info("Online evaluation configured successfully.")
        logger.info("Results will appear in CloudWatch metrics.")
    except Exception:
        logger.exception("Failed to configure online evaluation")


def main() -> None:
    parser = argparse.ArgumentParser(description="Configure online evaluation")
    parser.add_argument(
        "--agent-id",
        default=os.environ.get("AGENT_ID", "platform-agent"),
        help="AgentCore agent ID",
    )
    args = parser.parse_args()
    configure_online_evaluation(args.agent_id)


if __name__ == "__main__":
    main()
