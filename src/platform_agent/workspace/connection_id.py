"""Stable, content-addressed `connection_id` derivation.

A connection's identity is `(driver_type, normalized_endpoint, scope)`.
Two tabs that point at the same source produce the same id, so each
connection's durable store survives tab close and is rediscovered on
re-add (research.md R2).
"""

from __future__ import annotations

import hashlib

_DRIVER_NORMALIZATION = {
    "postgres": "postgresql",
    "rds": "postgresql",
}


def normalize_driver(driver_type: str) -> str:
    """Lowercase + alias-collapse so `postgres`/`rds` land on `postgresql`."""
    key = driver_type.strip().lower()
    return _DRIVER_NORMALIZATION.get(key, key)


def normalize_endpoint(driver_type: str, endpoint: str) -> str:
    """Driver-aware endpoint normalization.

    Snowflake account ids are case-insensitive; SQL hosts are case-sensitive
    in DNS but conventionally lowercased; Glue ARNs canonicalize on region.
    """
    normalized = endpoint.strip()
    drv = normalize_driver(driver_type)
    if drv in {"postgresql", "redshift", "snowflake", "iceberg", "databricks"}:
        normalized = normalized.lower()
    return normalized


def normalize_scope(scope: str) -> str:
    """Scopes are FQNs like `db.schema` or Glue DB names — lowercase + trim."""
    return scope.strip().lower()


def derive_connection_id(driver_type: str, endpoint: str, scope: str) -> str:
    """Return SHA-256 hex digest of the canonicalized connection identity."""
    canonical = "|".join(
        [
            normalize_driver(driver_type),
            normalize_endpoint(driver_type, endpoint),
            normalize_scope(scope),
        ]
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
