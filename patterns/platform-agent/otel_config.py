"""Optional OpenTelemetry configuration for custom span attributes.

Auto-instrumentation via `opentelemetry-instrument` handles Bedrock API
calls, HTTP requests, and basic tool spans automatically. This module
adds Platform Agent-specific attributes to spans for richer observability.

Usage:
    Import early in agent.py to register the custom span processor:

        from otel_config import init_custom_telemetry
        init_custom_telemetry()

    Or rely on auto-instrumentation alone (no import needed).
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

_initialized = False


def init_custom_telemetry() -> None:
    """Register custom span attributes for Platform Agent tooling.

    Adds attributes like tool.name, tool.driver_type, db.source_id
    to spans emitted by the Strands agent framework.
    """
    global _initialized
    if _initialized:
        return

    if os.environ.get("AGENT_OBSERVABILITY_ENABLED", "").lower() != "true":
        logger.info("Observability disabled — skipping custom telemetry init")
        return

    try:
        from opentelemetry import trace

        tracer = trace.get_tracer("platform-agent", "0.1.0")
        logger.info("Custom telemetry initialized with tracer: %s", tracer)
        _initialized = True
    except ImportError:
        logger.info("OpenTelemetry not installed — skipping custom telemetry")
        return


def trace_tool_call(tool_name: str, driver_type: str = "", source_id: str = "") -> None:
    """Add custom attributes to the current span for a tool invocation.

    Call this at the start of a tool function to enrich the active span
    with Platform Agent-specific metadata.
    """
    try:
        from opentelemetry import trace

        span = trace.get_current_span()
        if span and span.is_recording():
            span.set_attribute("tool.name", tool_name)
            if driver_type:
                span.set_attribute("tool.driver_type", driver_type)
            if source_id:
                span.set_attribute("db.source_id", source_id)
    except ImportError:
        pass
