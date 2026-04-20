"""Shared helpers for step handlers.

Keeps the individual step modules focused on step-specific logic. Everything
here is deterministic and test-friendly.
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Any

from ..drivers import DRIVER_REGISTRY, create_driver, get_driver

if TYPE_CHECKING:
    from ..api.deps import SessionContext
    from ..api.routes_workflow import SourceConnection

logger = logging.getLogger(__name__)


def source_id_for(session: "SessionContext", connection: "SourceConnection") -> str:
    """Build a stable source_id from the session UUID + driver type + database.

    Stable within a session, unique across sessions. Used as the driver-registry key.
    """
    return f"{session.session_id}_{connection.driver_type}_{connection.database}"


def ensure_driver(source_id: str, connection: "SourceConnection") -> Any:
    """Return a driver for ``source_id``, creating it if missing.

    Credentials live only in the request-scoped driver instance; nothing is
    persisted beyond the driver cache's lifetime (process memory).
    """
    try:
        return get_driver(source_id)
    except (KeyError, ValueError):
        pass  # driver not yet registered — fall through to create

    kwargs: dict[str, Any] = {
        "database": connection.database,
        "user": connection.user,
    }
    if connection.host:
        kwargs["host"] = connection.host
    if connection.account:
        kwargs["account"] = connection.account
    if connection.port:
        kwargs["port"] = connection.port
    if connection.schema:
        kwargs["schema"] = connection.schema
    if connection.role:
        kwargs["role"] = connection.role
    if connection.warehouse:
        kwargs["warehouse"] = connection.warehouse

    if connection.credential.kind == "password":
        kwargs["password"] = connection.credential.password
    elif connection.credential.kind == "sso_externalbrowser":
        kwargs["authenticator"] = "externalbrowser"

    if connection.driver_type not in DRIVER_REGISTRY:
        raise ValueError(
            f"Unknown driver '{connection.driver_type}'. "
            f"Registered: {sorted(DRIVER_REGISTRY)}"
        )

    return create_driver(
        driver_type=connection.driver_type,
        source_id=source_id,
        **kwargs,
    )


def scan_metadata_safe(source_id: str) -> dict[str, Any]:
    """Call driver.scan_metadata(); return {} if the driver lacks the method."""
    driver = get_driver(source_id)
    try:
        result = driver.scan_metadata()
    except Exception as exc:
        logger.warning("scan_metadata failed for %s: %s", source_id, exc)
        return {"tables": []}
    if not isinstance(result, dict):
        return {"tables": []}
    return result


def profile_safe(source_id: str) -> dict[str, Any]:
    """Call driver.profile_columns(); return {} on failure."""
    driver = get_driver(source_id)
    try:
        result = driver.profile_columns()
    except Exception as exc:
        logger.warning("profile_columns failed for %s: %s", source_id, exc)
        return {}
    return result if isinstance(result, dict) else {}


def short_summary(text: str, max_len: int) -> str:
    """Truncate to ``max_len`` with ellipsis, preserving word boundaries."""
    if len(text) <= max_len:
        return text
    truncated = text[: max_len - 1].rsplit(" ", 1)[0]
    return truncated + "…"


def sanitize_id(label: str) -> str:
    """Lowercase + snake_case + strip leading digits. Used for entity IDs."""
    slug = re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_")
    if slug and slug[0].isdigit():
        slug = f"e_{slug}"
    return slug or "entity"
