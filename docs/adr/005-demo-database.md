# ADR-005: Demo Database

**Status**: Accepted

**Date**: 2026-03-21

## Context

The agent needs a sample database for development, testing, and live demos. The dataset must have well-defined business processes (orders, customers, products), clear foreign key relationships for dimensional modeling, and be fast to provision and load.

## Options Considered

1. **Amazon RDS PostgreSQL with Northwinds** — Classic order-management dataset (13+ tables, 830 orders). Available as a SQL script, loads in seconds via `psql`. Standard `information_schema` for metadata profiling. Free-tier eligible on db.t3.micro.
2. **Amazon RDS PostgreSQL with TPC-H** — Industry-standard benchmark dataset. Larger and more complex, but synthetic data lacks intuitive business context for demos.
3. **Amazon Athena with S3/Glue** — Serverless lakehouse setup. More complex provisioning (S3 bucket, Glue crawler, Athena workgroup). Better for Phase 2 service expansion.
4. **Amazon Redshift Serverless** — Closest to traditional DW. Higher cost and longer provisioning time for a demo environment.

## Decision

Use **Amazon RDS for PostgreSQL 16** with the **Northwinds dataset** as the primary demo database. Instance: `db.t3.micro`, single-AZ, publicly accessible, deployed in the `phdata-dev-vpc` VPC in `us-east-1`.

## Consequences

- **Positive**: Fastest data loading — single `psql -f northwind.sql` command, under 60 seconds.
- **Positive**: Universal familiarity — PostgreSQL is widely understood across phData's customer base.
- **Positive**: Standard `information_schema` and `pg_catalog` — no service-specific translation needed for Toolkit profiling.
- **Positive**: Free-tier eligible, negligible cost for demo use.
- **Negative**: Northwinds is small (830 orders) and may feel like a "toy database" to sophisticated audiences. TPC-H is prepared as a follow-up option.
- **Negative**: Public accessibility for demo convenience creates a security trade-off. Acceptable for demo data; production deployments must use private subnets.
