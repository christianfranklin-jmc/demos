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
  BackendEntity,
  BackendRelationship,
  BackendLogicalTable,
  BackendLogicalField,
  // DSA
  PRDArtifact,
  ConceptualModelArtifact,
  ConceptualEntity,
  EntityRelationship,
  LogicalModelArtifact,
  LogicalEntity,
  LogicalAttribute,
  EntityRole,
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

  return {
    business_objective: find("problem") ?? find("goal"),
    current_state_pain: find("problem") ?? find("current state"),
    success_criteria: find("goal") ?? find("success"),
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
