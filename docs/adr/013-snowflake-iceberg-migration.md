# ADR-013: Snowflake → AWS Migration via Apache Iceberg

**Status**: Accepted

**Date**: 2026-03-27

## Context

The Migration Agent needs to extract schemas and data from Snowflake and land them on AWS in a queryable format. The target format must be open (not proprietary), support time travel and schema evolution, and be queryable by multiple AWS engines (Athena, Redshift Spectrum, EMR).

## Options Considered

1. **Direct Parquet on S3** — Simple but lacks time travel, schema evolution, and ACID semantics. Requires manual partitioning.
2. **Apache Iceberg on S3** — Open table format with ACID transactions, time travel, schema evolution, partition evolution. Native support in Athena, EMR, Glue, and Redshift Spectrum.
3. **Delta Lake on S3** — Similar capabilities to Iceberg but tighter Databricks coupling. Less native AWS support.
4. **Apache Hudi on S3** — Good for incremental upserts but more complex setup. Better for streaming use cases.

## Decision

**Apache Iceberg** on S3 with Glue Data Catalog as the metadata store. Data lands as Parquet files; Glue Catalog stores the Iceberg table metadata. Snowflake clustering keys map to Iceberg partition transforms. The Migration Agent generates Iceberg DDL, triggers Glue ETL for data export, and registers tables in Glue Catalog.

## Consequences

**Positive:**
- Open format — no vendor lock-in. Queryable by Athena, Redshift Spectrum, EMR, Spark.
- Schema evolution without rewriting data.
- Partition evolution — change partitioning strategy without rewriting existing data.
- Time travel — query historical versions.
- Glue Catalog integration is native and well-documented.

**Negative:**
- Snowflake → Iceberg type mapping requires careful handling (VARIANT, OBJECT, ARRAY → string).
- Glue ETL job for data export adds latency and cost vs. direct S3 COPY.
- Small files problem for high-cardinality partitions — needs compaction.
