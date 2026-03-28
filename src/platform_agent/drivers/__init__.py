"""Multi-database driver registry.

Provides a DatabaseDriver protocol and a registry of implementations.
Tools program against the protocol; adding a new database = one new file.
"""

from __future__ import annotations

from typing import Any

from .base import DatabaseDriver
from .postgresql import PostgreSQLDriver

# Registry of available drivers — import conditionally to avoid
# requiring all connector packages at install time.
DRIVER_REGISTRY: dict[str, type[DatabaseDriver]] = {
    "postgresql": PostgreSQLDriver,
}

# Lazy-register optional drivers
try:
    from .redshift import RedshiftDriver
    DRIVER_REGISTRY["redshift"] = RedshiftDriver
except ImportError:
    pass

try:
    from .snowflake import SnowflakeDriver
    DRIVER_REGISTRY["snowflake"] = SnowflakeDriver
except ImportError:
    pass

# Active driver instances keyed by source_id
_drivers: dict[str, DatabaseDriver] = {}


def create_driver(driver_type: str, source_id: str, **kwargs: Any) -> DatabaseDriver:
    """Create, connect, and register a driver instance."""
    if driver_type not in DRIVER_REGISTRY:
        available = list(DRIVER_REGISTRY.keys())
        raise ValueError(f"Unknown driver_type '{driver_type}'. Available: {available}")

    cls = DRIVER_REGISTRY[driver_type]
    driver = cls(**kwargs)
    driver.connect()
    _drivers[source_id] = driver
    return driver


def get_driver(source_id: str) -> DatabaseDriver:
    """Retrieve a registered driver by source_id."""
    if source_id not in _drivers:
        available = list(_drivers.keys())
        raise ValueError(f"No driver for source_id '{source_id}'. Available: {available}")
    return _drivers[source_id]


def list_sources() -> list[str]:
    """Return all registered source_ids."""
    return list(_drivers.keys())


__all__ = [
    "DatabaseDriver",
    "PostgreSQLDriver",
    "DRIVER_REGISTRY",
    "create_driver",
    "get_driver",
    "list_sources",
]
