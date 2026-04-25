// Backend-payload → DSA-artifact adapters.
//
// The backend's SSE payloads (mirroring src/platform_agent/api/events.py) do
// not match DSA's artifact shapes one-for-one. This module defines the
// lossy-but-sensible conversion used by useAgent when rendering live results
// into AppContext's reducer. Keep the mappings defensive: any backend field
// that the DSA UI cannot render is dropped here, not inside the reducer.

import type {
  // backend
  PrdPayload as BackendPrd,
  ConceptualModelPayload as BackendConceptual,
  LogicalModelPayload as BackendLogical,
  DetailedRequirementsPayload as BackendDetailed,
  BackendEntity,
  BackendRelationship,
  BackendLogicalTable,
  BackendLogicalField,
  BackendDetailedTable,
  BackendDetailedField,
  // DSA
  PRDArtifact,
  ConceptualModelArtifact,
  ConceptualEntity,
  EntityRelationship,
  LogicalModelArtifact,
  LogicalEntity,
  LogicalAttribute,
  EntityRole,
  DetailedRequirementsArtifact,
  DetailedField,
  SourceSystem,
  ConsumerPersona,
  MetricDefinition,
  TimeRange,
  AcceptanceCriterion,
} from "./types";

// ─── PRD ───

export function prdFromBackend(payload: BackendPrd): Partial<PRDArtifact> {
  const find = (heading: string) =>
    payload.sections.find((s) => s.heading.toLowerCase().includes(heading.toLowerCase()))?.body ??
    null;

  const scopeOut = find("out of scope");
  const scopeOutList = scopeOut
    ? scopeOut
        .split(/[.\n]/)
        .map((s) => s.trim())
        .filter(Boolean)
    : null;

  // Harvest cited tables for downstream derivation.
  const cited = Array.from(
    new Set(payload.sections.flatMap((s) => s.cited_tables)),
  );
  const scopeIn = cited.length ? cited : null;
  const sourceSchemas = Array.from(
    new Set(cited.map((t) => t.split(".")[0]).filter(Boolean)),
  );
  const sourceSystems: SourceSystem[] | null = sourceSchemas.length
    ? sourceSchemas.map((s) => ({
        system: `RDS PostgreSQL · ${s}`,
        data_domain: "Sales & Operations",
        access_confirmed: true,
      }))
    : null;

  // Fill EVERY PRD field so the first page renders a complete draft
  // instead of a mostly-empty form. Fixed defaults are chosen for the
  // Northwinds sales/operations scenario; user edits via UPDATE_PRD
  // replace them cleanly.
  const firstTable = cited[0]?.split(".").pop() ?? "record";

  const primaryConsumers: ConsumerPersona[] = [
    { persona: "Data Analyst", role: "Self-service insights", access_level: "Full read" },
    { persona: "Revenue Operations", role: "Performance reporting", access_level: "Full read" },
    { persona: "Product Manager", role: "Trend discovery", access_level: "Curated dashboards" },
  ];

  const keyMetrics: MetricDefinition[] = [
    {
      name: "Total Revenue",
      definition: "Sum of unit_price × quantity across all order lines",
      formula: "SUM(od.unit_price * od.quantity * (1 - od.discount))",
      priority: "MVP",
    },
    {
      name: "Order Count",
      definition: "Number of distinct orders placed in the period",
      formula: "COUNT(DISTINCT o.order_id)",
      priority: "MVP",
    },
    {
      name: "Average Order Value",
      definition: "Total Revenue divided by Order Count",
      formula: "total_revenue / order_count",
      priority: "MVP",
    },
    {
      name: "Customer Retention Rate",
      definition: "Share of customers active in both current and prior period",
      formula: "retained_customers / prior_period_customers",
      priority: "Phase 2",
    },
  ];

  const timeRange: TimeRange = {
    historical_coverage: "3 years rolling",
    refresh_cadence: "Daily by 06:00 UTC",
    snapshot_logic: "End-of-day close",
    fiscal_calendar: "Gregorian; Q1 = Jan–Mar",
  };

  const acceptanceCriteria: AcceptanceCriterion[] = [
    {
      criterion: "Revenue totals reconcile to the source within 0.1%",
      test_method: "Reconciliation query vs. information_schema row counts",
      owner: "Data Engineering",
    },
    {
      criterion: "Every dimension row joins to a live FK target",
      test_method: "dbt relationships test on each mart",
      owner: "Analytics Engineering",
    },
    {
      criterion: "Daily refresh completes by 06:00 UTC with zero failed models",
      test_method: "dbt run telemetry + scheduler alert",
      owner: "Data Platform",
    },
  ];

  return {
    // ── Business Objective ──
    business_objective: find("problem"),
    current_state_pain:
      "Today these questions require manual SQL across disparate source tables with inconsistent joins, grain, and naming. Analysts spend hours per request and answers vary across teams.",
    decisions_enabled: [
      "Prioritize high-value customer cohorts",
      "Identify product categories with declining sales",
      "Forecast territory-level demand",
      "Allocate supplier and shipper capacity",
    ],

    // ── Consumers ──
    primary_consumers: primaryConsumers,
    secondary_consumers: "Finance, Marketing, and Supply Chain stakeholders",

    // ── Data Scope ──
    grain_statement: `One row per ${firstTable}`,
    time_range: timeRange,

    // ── Key Metrics ──
    key_metrics: keyMetrics,

    // ── Source Systems ──
    source_systems: sourceSystems,

    // ── Success Criteria ──
    success_criteria: find("goal") ?? find("success"),
    acceptance_criteria: acceptanceCriteria,
    constraints:
      "Conform to org data-governance policy. No PII in published marts. Revenue must be derived identically across all views (single source of truth).",

    // ── Scope ──
    scope_in: scopeIn,
    scope_out: scopeOutList,

    completeness_score: Math.round(payload.completeness * 100),
  };
}

// ─── Conceptual Model ───

function inferRole(entity: BackendEntity): EntityRole {
  // Backend doesn't emit a fact/dim/ref role. Use naming heuristics:
  //   *_fact / fct_* / orders / sales / transactions → FACT
  //   *_dim / dim_* / *_ref → DIM
  //   everything else → DIM (default; safer than FACT)
  const n = entity.source_table.toLowerCase();
  if (/(^fct_|_fact$|orders|sales|transactions|events|invoices)/.test(n)) return "FACT";
  if (/(_ref$|^ref_)/.test(n)) return "REF";
  return "DIM";
}

export function conceptualFromBackend(payload: BackendConceptual): ConceptualModelArtifact {
  const byId = new Map<string, BackendEntity>();
  payload.entities.forEach((e) => byId.set(e.id, e));

  const entities: ConceptualEntity[] = payload.entities.map((e) => ({
    entity_id: e.id,
    entity_name: e.label,
    role: inferRole(e),
    description: `Source: ${e.source_table}${
      e.row_count_est != null ? ` (~${e.row_count_est.toLocaleString()} rows)` : ""
    }`,
    abstract_attributes: e.key_columns.length
      ? e.key_columns.slice(0, 3)
      : ["Primary key TBD"],
    cardinality_hint: null,
  }));

  const relationships: EntityRelationship[] = payload.relationships.map(
    (r: BackendRelationship) => ({
      from_entity: byId.get(r.from_entity_id)?.label ?? r.from_entity_id,
      verb: verbForCardinality(r.cardinality, r.inferred),
      to_entity: byId.get(r.to_entity_id)?.label ?? r.to_entity_id,
    }),
  );

  return { entities, relationships };
}

function verbForCardinality(card: BackendRelationship["cardinality"], inferred: boolean): string {
  const base = {
    "1:1": "has one",
    "1:N": "has many",
    "N:1": "belongs to",
    "N:M": "relates to",
  }[card];
  return inferred ? `${base} (inferred)` : base;
}

// ─── Logical Model ───

function mapLogicalField(field: BackendLogicalField): LogicalAttribute {
  const samples = field.sample_values.slice(0, 3).join(", ");
  return {
    target_field: field.name,
    data_type: normalizeType(field.data_type),
    source_field: field.name,
    transformation_rule: samples ? `e.g. ${samples}` : null,
    flag: null,
  };
}

function normalizeType(raw: string): string {
  const low = raw.toLowerCase();
  if (low.includes("int")) return "INT";
  if (low.includes("char") || low.includes("text")) return "VARCHAR";
  if (low.includes("decimal") || low.includes("numeric") || low.includes("money")) return "DECIMAL";
  if (low.includes("date")) return "DATE";
  if (low.includes("time")) return "TIMESTAMP";
  if (low.includes("bool")) return "BOOLEAN";
  return raw.toUpperCase();
}

function inferLogicalRole(table: BackendLogicalTable): EntityRole {
  const hasMeasure = table.fields.some((f) => f.role === "measure" || f.is_measure);
  if (hasMeasure) return "FACT";
  return "DIM";
}

export function logicalFromBackend(payload: BackendLogical): LogicalModelArtifact {
  const entities: LogicalEntity[] = payload.tables.map((t) => ({
    entity_name: t.label,
    role: inferLogicalRole(t),
    attributes: t.fields.map(mapLogicalField),
  }));
  return { entities, flags: [] };
}

// ─── Detailed Requirements (Step 4) ───

function backendDetailedFieldToDsa(
  f: BackendDetailedField,
): DetailedField {
  return {
    target_field: f.target_field,
    data_type: normalizeType(f.data_type),
    source_system: "northwinds",
    source_field: f.source_field ?? f.target_field,
    transformation: "pass-through",
    business_rule: "",
    required: true,
    governance: "Public",
    phase: "MVP",
  };
}

function backendDetailedTableToDsaFact(t: BackendDetailedTable): {
  table_name: string;
  grain: string;
  fields: DetailedField[];
} {
  return {
    table_name: t.table_name,
    grain: t.grain ?? "one row per record",
    fields: t.fields.map(backendDetailedFieldToDsa),
  };
}

function backendDetailedTableToDsaDim(t: BackendDetailedTable): {
  table_name: string;
  fields: DetailedField[];
} {
  return {
    table_name: t.table_name,
    fields: t.fields.map(backendDetailedFieldToDsa),
  };
}

export function detailedFromBackend(
  payload: BackendDetailed,
): DetailedRequirementsArtifact {
  const fact = payload.fact_table
    ? backendDetailedTableToDsaFact(payload.fact_table)
    : { table_name: "(no fact identified)", grain: "—", fields: [] };
  const dims = payload.dimension_tables.map(backendDetailedTableToDsaDim);
  return {
    fact_table: fact,
    dimension_tables: dims,
    calculated_metrics: [],
    completeness_score: dims.length ? 70 : 40,
  };
}
