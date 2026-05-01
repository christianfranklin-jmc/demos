# dbt Project Templates

dbt projects emitted by the provisioning `model-agent` (and the
existing `generate_dbt_project` tool) MUST follow this layout per
Constitution Addendum B + Kimball.

## Layout

```
<project>/
  dbt_project.yml          # standard
  profiles.yml             # adapter selected by the target driver
  models/
    staging/
      stg_<conn>__<src>.sql      # one per source table
    intermediate/
      int_<fact>_<purpose>.sql   # join + transform
    marts/
      <fct_or_dim>.sql           # consumer-visible
  tests/
    schema.yml                   # not_null / unique / relationships
```

## Materialization

- Staging: `materialized: 'view'` by default.
- Intermediate: `materialized: 'ephemeral'` unless reused by ≥2 marts.
- Marts: `materialized: 'incremental'` for fact tables; `'table'` for
  dimensions.
- Iceberg targets: emit dbt-glue profile + `file_format='iceberg'`
  configs at the marts layer.

## Sources

- Use `source()` references — never literal table names — so the
  per-connection driver can rewrite them at compile time.
- One `source` block per connection's process schema.
