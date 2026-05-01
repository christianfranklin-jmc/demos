# Approved Metric Definitions

Metrics MUST be defined once per target connection's semantic graph and
referenced by name from every consumer. New metrics land via the
provisioning flow's `semantic-agent` (FR-025); ad-hoc redefinitions are
flagged by the redundancy gate (ADR-019).

## Format

- Lower `snake_case` name.
- MetricFlow-compatible `definition_sql` (SELECT/WITH only — no writes).
- `entity_ids` referencing the metric's host entity(ies) **within the same
  connection** (Q2 — no cross-connection metrics in v1).
- Optional `unit` (`usd`, `count`, `percent`, `bps`).

## Example

```yaml
name: gross_fee_revenue_q1
definition_sql: |
  SELECT SUM(amount) FROM billing.fee_invoice
  WHERE invoice_date BETWEEN '2026-01-01' AND '2026-03-31'
entity_ids: ["e_billing_fee_invoice"]
unit: usd
```

## Reuse policy

The redundancy gate flags name collisions against the target connection's
existing metric list. Reuse is the default; override requires a rationale.
