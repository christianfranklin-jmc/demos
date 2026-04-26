# Iceberg Table Standards

Iceberg-backed data products (the terminal artifact of every
provisioning run) MUST follow these conventions.

## Glue catalog identity

- Glue database: `dsa_hub_<scope>_<purpose>` (e.g.,
  `dsa_hub_pinnacle_360`).
- One Glue DB per `IcebergDataProduct` connection in the workspace.

## Partitioning

- Time-partitioned facts: `PARTITIONED BY (days(event_date))` where the
  fact has a daily grain (e.g., `account_aum_daily`).
- Period-partitioned facts: `PARTITIONED BY (period_id)` where the
  grain matches the `gl.PERIOD` table.
- Dimensions: not partitioned (full scan is cheaper than directory
  metadata for low-cardinality tables).

## Sort orders

- Facts: sort by `(grain_dimension_id, event_date)` so range scans
  are I/O-efficient.
- Dimensions: sort by `id` for deterministic compaction.

## Retention

- Snapshot retention: 60 days (`history.expire.max-snapshot-age-ms = 5184000000`).
- Min snapshots: 5 (`history.expire.min-snapshots-to-keep = 5`).
- Compact at ≥ 64 MB target file size.

## Catalog property defaults

```
write.format.default = parquet
write.parquet.compression-codec = zstd
write.metadata.previous-versions-max = 10
```
