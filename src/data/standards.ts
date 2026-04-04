/**
 * DSA Standards — Best practice guidelines per step.
 * These define "what good looks like" for each artifact type.
 * Used by:
 *   - StandardsView: displays rules to the user
 *   - validation.ts: validates field edits against these rules
 */

import type { StepNumber, FlagType } from "../lib/types";

export interface Standard {
  id: string;
  step: StepNumber;
  category: string;
  rule: string;
  description: string;
  severity: "error" | "warning" | "info";
  fieldKey?: string;
  flagType: FlagType;
  validate?: (value: any) => boolean; // true = passes
}

export const STANDARDS: Standard[] = [
  // ─── Step 1: PRD Standards ───
  {
    id: "s1-01",
    step: 1,
    category: "Business Objective",
    rule: "Objective must be outcome-oriented, not activity-oriented",
    description: "A good objective answers 'what decision will this enable?' not 'what report will this produce?' Avoid vague terms like 'track', 'monitor', 'view'. Use action verbs like 'optimize', 'reduce', 'increase'.",
    severity: "error",
    fieldKey: "business_objective",
    flagType: "standards_vague_objective",
    validate: (v: any) => {
      if (!v || typeof v !== "string") return true; // skip if empty
      const vague = ["track", "monitor", "view", "see", "look at", "dashboard"];
      const lower = v.toLowerCase();
      return !vague.some((w) => lower.startsWith(w) || lower === w);
    },
  },
  {
    id: "s1-02",
    step: 1,
    category: "Business Objective",
    rule: "Objective must be at least 20 characters",
    description: "One-word or very short objectives lack the specificity needed to scope the data product. Aim for a complete sentence.",
    severity: "warning",
    fieldKey: "business_objective",
    flagType: "standards_vague_objective",
    validate: (v: any) => !v || typeof v !== "string" || v.length >= 20,
  },
  {
    id: "s1-03",
    step: 1,
    category: "Data Scope",
    rule: "Primary grain must be explicitly defined",
    description: "The grain statement should specify exactly what one row represents. Without this, every downstream join is ambiguous.",
    severity: "error",
    fieldKey: "grain_statement",
    flagType: "standards_missing_grain",
    validate: (v: any) => !v || (typeof v === "string" && v.toLowerCase().includes("per")),
  },
  {
    id: "s1-04",
    step: 1,
    category: "Key Metrics",
    rule: "At least 3 key metrics must be defined",
    description: "Fewer than 3 metrics suggests incomplete requirements. Each metric should have a name and definition.",
    severity: "warning",
    fieldKey: "key_metrics",
    flagType: "standards_undefined_metric",
    validate: (v: any) => !v || !Array.isArray(v) || v.length >= 3,
  },
  {
    id: "s1-05",
    step: 1,
    category: "Key Metrics",
    rule: "Each metric should have a formula or calculation method",
    description: "Metrics without formulas create ambiguity during implementation. Even 'COUNT of X' is better than nothing.",
    severity: "info",
    fieldKey: "key_metrics",
    flagType: "standards_undefined_metric",
    validate: (v: any) => {
      if (!v || !Array.isArray(v)) return true;
      return v.every((m: any) => m.formula || m.definition?.length > 10);
    },
  },
  {
    id: "s1-06",
    step: 1,
    category: "Success Criteria",
    rule: "Success criteria must be measurable and time-bound",
    description: "Vague criteria like 'works correctly' are not testable. Include specific numbers, percentages, or SLA targets.",
    severity: "warning",
    fieldKey: "success_criteria",
    flagType: "standards_weak_criteria",
    validate: (v: any) => {
      if (!v || typeof v !== "string") return true;
      const measurable = /\d+|%|percent|within|less than|greater than|before|by|hours?|days?|weeks?/i;
      return measurable.test(v);
    },
  },
  {
    id: "s1-07",
    step: 1,
    category: "Consumers",
    rule: "At least one primary consumer persona must be identified",
    description: "A data product without identified consumers has no clear owner for feedback and validation.",
    severity: "error",
    fieldKey: "primary_consumers",
    flagType: "standards_general",
    validate: (v: any) => !v || (Array.isArray(v) && v.length > 0),
  },
  {
    id: "s1-08",
    step: 1,
    category: "Constraints",
    rule: "PII and governance constraints must be documented",
    description: "Every data product must address data sensitivity. Even 'no PII involved' is a valid constraint.",
    severity: "warning",
    fieldKey: "constraints",
    flagType: "standards_no_governance",
    validate: (v: any) => !v || (typeof v === "string" && v.length >= 5),
  },

  // ─── Step 2: Conceptual Model Standards ───
  {
    id: "s2-01",
    step: 2,
    category: "Entity Design",
    rule: "Every model must have at least one fact table",
    description: "A dimensional model without a fact table has no measurable business process to analyze.",
    severity: "error",
    flagType: "standards_general",
  },
  {
    id: "s2-02",
    step: 2,
    category: "Entity Design",
    rule: "Entity names must follow snake_case naming convention",
    description: "Consistent naming prevents join errors and aligns with Snowflake conventions. Use dim_ prefix for dimensions, fact_ for facts.",
    severity: "warning",
    flagType: "standards_general",
  },
  {
    id: "s2-03",
    step: 2,
    category: "Relationships",
    rule: "Every dimension must relate to at least one fact table",
    description: "Orphan dimensions add complexity without value. If a dimension has no relationship, it may not be needed.",
    severity: "warning",
    flagType: "standards_general",
  },

  // ─── Step 3: Logical Model Standards ───
  {
    id: "s3-01",
    step: 3,
    category: "Field Design",
    rule: "Every field must have an explicit data type",
    description: "Implicit data types cause casting errors and performance issues in the warehouse.",
    severity: "error",
    flagType: "standards_general",
  },
  {
    id: "s3-02",
    step: 3,
    category: "Source Mapping",
    rule: "Source field must be documented for every non-derived field",
    description: "Fields without source mappings cannot be implemented. Even 'TBD' is better than blank.",
    severity: "warning",
    flagType: "standards_general",
  },
  {
    id: "s3-03",
    step: 3,
    category: "Quality",
    rule: "All quality flags must be resolved or deferred before approval",
    description: "Open flags represent unresolved design decisions. Defer is acceptable; ignoring is not.",
    severity: "error",
    flagType: "standards_general",
  },

  // ─── Step 4: Detailed Requirements Standards ───
  {
    id: "s4-01",
    step: 4,
    category: "Governance",
    rule: "Every field must have a governance level assigned",
    description: "Governance levels (Public, Restricted, Masked, Excluded) determine who can see what. Missing governance = security risk.",
    severity: "error",
    flagType: "standards_no_governance",
  },
  {
    id: "s4-02",
    step: 4,
    category: "Phasing",
    rule: "Every field must be assigned to a phase (MVP, Phase 2, Out of scope)",
    description: "Unphased fields create scope creep. Explicitly mark everything as in or out.",
    severity: "warning",
    flagType: "standards_general",
  },
  {
    id: "s4-03",
    step: 4,
    category: "Business Rules",
    rule: "Derived fields must have a documented formula",
    description: "Calculated metrics without formulas cannot be implemented consistently.",
    severity: "error",
    flagType: "standards_undefined_metric",
  },
  {
    id: "s4-04",
    step: 4,
    category: "Completeness",
    rule: "Minimum 60% field coverage required for approval",
    description: "Approving with less than 60% field mapping coverage means significant gaps remain.",
    severity: "warning",
    flagType: "standards_general",
  },
];

export function getStandardsForStep(step: StepNumber): Standard[] {
  return STANDARDS.filter((s) => s.step === step);
}

export function getStandardsByCategory(step: StepNumber): Record<string, Standard[]> {
  const standards = getStandardsForStep(step);
  const grouped: Record<string, Standard[]> = {};
  for (const s of standards) {
    if (!grouped[s.category]) grouped[s.category] = [];
    grouped[s.category].push(s);
  }
  return grouped;
}
