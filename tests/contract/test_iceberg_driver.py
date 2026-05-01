"""Contract tests for IcebergDriver (T018).

Pure-Python tests that exercise the protocol surface without hitting
AWS. The connect() / scan_metadata() / execute_query() AWS-touching
paths are covered by an integration test under
``tests/integration/test_iceberg_driver_aws.py`` (deferred — requires
credentials), gated on the ``slow`` pytest marker.
"""

from __future__ import annotations

import pytest


def test_driver_registered_under_iceberg_key():
    from platform_agent.drivers import DRIVER_REGISTRY

    assert "iceberg" in DRIVER_REGISTRY


def test_driver_type_attribute():
    from platform_agent.drivers.iceberg import IcebergDriver

    d = IcebergDriver(
        glue_database="dsa_hub_pinnacle_360",
        warehouse_s3_uri="s3://example/warehouse",
    )
    assert d.driver_type == "iceberg"


def test_dbt_adapter_returns_glue():
    from platform_agent.drivers.iceberg import IcebergDriver

    d = IcebergDriver(
        glue_database="dsa_hub_pinnacle_360",
        warehouse_s3_uri="s3://example/warehouse",
    )
    assert d.get_dbt_adapter() == "glue"


def test_dbt_profile_shape_matches_dbt_glue():
    from platform_agent.drivers.iceberg import IcebergDriver

    d = IcebergDriver(
        glue_database="dsa_hub_pinnacle_360",
        warehouse_s3_uri="s3://example/warehouse",
        region="us-west-2",
    )
    profile = d.get_dbt_profile()
    assert profile["type"] == "glue"
    assert profile["region"] == "us-west-2"
    assert profile["schema"] == "dsa_hub_pinnacle_360"
    assert profile["location"] == "s3://example/warehouse"


def test_destructive_ddl_is_unconditionally_blocked():
    from platform_agent.drivers.iceberg import IcebergDriver

    d = IcebergDriver(
        glue_database="dsa_hub_pinnacle_360",
        warehouse_s3_uri="s3://example/warehouse",
    )
    for stmt in (
        "DROP TABLE dsa_hub_pinnacle_360.fct_client_360",
        "TRUNCATE TABLE foo",
        "ALTER TABLE foo ADD COLUMN bar int",
    ):
        with pytest.raises(ValueError, match="blocked"):
            d.execute_ddl(stmt)


def test_create_table_passes_through():
    from platform_agent.drivers.iceberg import IcebergDriver

    d = IcebergDriver(
        glue_database="dsa_hub_pinnacle_360",
        warehouse_s3_uri="s3://example/warehouse",
    )
    out = d.execute_ddl("CREATE TABLE iceberg.dsa_hub_pinnacle_360.fct_x (id int)")
    assert out["status"] == "noop"  # registration goes via pyiceberg in mapping-agent


def test_execute_query_blocks_writes_via_read_only_helper():
    from platform_agent.drivers.iceberg import IcebergDriver
    from platform_agent.workspace.read_only import ReadOnlyViolation

    d = IcebergDriver(
        glue_database="dsa_hub_pinnacle_360",
        warehouse_s3_uri="s3://example/warehouse",
    )
    with pytest.raises(ReadOnlyViolation):
        d.execute_query("DELETE FROM foo", max_rows=10)


def test_execute_query_rejects_complex_sql_with_friendly_error():
    """v1 driver does literal FROM<table> matching; complex SQL falls back to DuckDB."""
    from platform_agent.drivers.iceberg import IcebergDriver

    d = IcebergDriver(
        glue_database="dsa_hub_pinnacle_360",
        warehouse_s3_uri="s3://example/warehouse",
    )
    # No FROM clause → friendly NotImplementedError
    with pytest.raises(NotImplementedError, match="DuckDB scratchpad"):
        d.execute_query("SELECT 1", max_rows=10)
