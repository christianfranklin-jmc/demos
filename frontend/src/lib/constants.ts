import type { StepConfig, GateConfig, StepNumber } from "./types";

// ============================================================
// Step Configuration
// ============================================================

export const STEPS: StepConfig[] = [
  {
    step: 0,
    name: "Stakeholder Alignment",
    agent_persona: "Stakeholder Prep Agent",
    artifact_type: "stakeholder_map",
    tab_name: "Stakeholder Map",
    gate_name: null,
    approver_persona: null,
    system_prompt_path: "step0-stakeholder",
  },
  {
    step: 1,
    name: "Requirements",
    agent_persona: "Requirements Agent",
    artifact_type: "prd",
    tab_name: "PRD Draft",
    gate_name: "PRD Review",
    approver_persona: "data_product_owner",
    system_prompt_path: "step1-requirements",
  },
  {
    step: 2,
    name: "Conceptual Model",
    agent_persona: "Conceptual Modeler",
    artifact_type: "conceptual_model",
    tab_name: "Conceptual Model",
    gate_name: "Conceptual Model Review",
    approver_persona: "analytics_engineer",
    system_prompt_path: "step2-conceptual",
  },
  {
    step: 3,
    name: "Logical Model",
    agent_persona: "Logical Modeler",
    artifact_type: "logical_model",
    tab_name: "Logical Model",
    gate_name: "Logical Model Review",
    approver_persona: "analytics_engineer",
    system_prompt_path: "step3-logical",
  },
  {
    step: 4,
    name: "Detailed Requirements",
    agent_persona: "Requirements Finalizer",
    artifact_type: "detailed_requirements",
    tab_name: "Detailed Requirements",
    gate_name: "Final Requirements Review",
    approver_persona: "data_product_owner",
    system_prompt_path: "step4-detailed",
  },
];

// ============================================================
// Gate Configuration
// ============================================================

export const GATES: GateConfig[] = [
  {
    step: 1,
    gate_name: "PRD Review",
    approver_persona: "data_product_owner",
    approver_description: "Product Owner reviews and approves the PRD before conceptual modeling begins.",
    hard_block_on_flags: false,
    soft_warn_threshold: 80,
  },
  {
    step: 2,
    gate_name: "Conceptual Model Review",
    approver_persona: "analytics_engineer",
    approver_description: "Analytics Engineer reviews entity relationships and naming before logical expansion.",
    hard_block_on_flags: false,
    soft_warn_threshold: 0,
  },
  {
    step: 3,
    gate_name: "Logical Model Review",
    approver_persona: "analytics_engineer",
    approver_description: "Analytics Engineer confirms all flags resolved before detailed field mapping.",
    hard_block_on_flags: true, // Soft block — "Resolve Flags First" replaces Approve when flags > 0
    soft_warn_threshold: 0,
  },
  {
    step: 4,
    gate_name: "Final Requirements Review",
    approver_persona: "data_product_owner",
    approver_description: "Product Owner gives final approval on the complete data requirements package.",
    hard_block_on_flags: false,
    soft_warn_threshold: 0,
  },
];

// ============================================================
// Completeness Weights (Step 1 PRD)
// ============================================================

export const PRD_COMPLETENESS_WEIGHTS: Record<string, number> = {
  business_objective: 20,
  consumers: 10,
  grain: 20,
  time_range: 10,
  key_metrics: 20,
  success_criteria: 15,
  constraints: 5,
};

export const GATE_UNLOCK_THRESHOLD = 80;

// ============================================================
// Interview Sequence (Step 1)
// ============================================================

export const INTERVIEW_SEQUENCE = [
  "business_objective",
  "consumers",
  "decisions_enabled",
  "grain",
  "time_range",
  "key_metrics",
  "source_systems",
  "success_criteria",
  "constraints",
] as const;

// ============================================================
// Layout Constants
// ============================================================

export const LAYOUT = {
  SIDEBAR_WIDTH: 264,
  CONTEXT_BAR_HEIGHT: 44,
  GATE_BANNER_HEIGHT: 64,
  CHAT_PANEL_RATIO: 0.42,
  ARTIFACT_PANEL_RATIO: 0.58,
} as const;

// ============================================================
// Timing Constants
// ============================================================

export const TIMING = {
  TYPING_INDICATOR_DELAY: 400,
  TYPING_INDICATOR_THINKING: 800,
  FIELD_HIGHLIGHT_DURATION: 300,
  COMPLETENESS_ANIMATION: 300,
  GATE_CONFIRM_CHECKMARK: 800,
  GATE_COLLAPSE_DURATION: 300,
  SUGGESTED_REPLY_STAGGER: 50,
  SUGGESTED_REPLY_APPEAR_DELAY: 150,
} as const;

// ============================================================
// Entity Type Colors (Step 2 — border only, bg stays white)
// ============================================================

export const ENTITY_COLORS: Record<string, string> = {
  FACT: "#BFDBFE",    // blue-tinted
  DIM: "#99F6E4",     // teal-tinted
  REF: "#FDE68A",     // amber-tinted
  PRIMARY: "#3DDBB8", // full DSA teal
};

// ============================================================
// Flag Type Config
// ============================================================

export const FLAG_CONFIG: Record<string, { color: string; label: string }> = {
  grain_ambiguity: { color: "#D97706", label: "Grain Ambiguity" },
  access_dependency: { color: "#D97706", label: "Access Dependency" },
  missing_source: { color: "#EF4444", label: "Missing Source" },
  derived_field: { color: "#3B82F6", label: "Derived Field" },
  naming_conflict: { color: "#9CA3AF", label: "Naming Conflict" },
  // Standards violation flags (purple)
  standards_vague_objective: { color: "#8B5CF6", label: "Vague Objective" },
  standards_missing_grain: { color: "#8B5CF6", label: "Missing Grain Definition" },
  standards_weak_criteria: { color: "#8B5CF6", label: "Weak Success Criteria" },
  standards_undefined_metric: { color: "#8B5CF6", label: "Undefined Metric" },
  standards_no_governance: { color: "#8B5CF6", label: "No Governance Level" },
  standards_general: { color: "#8B5CF6", label: "Standards Violation" },
};

// ============================================================
// Demo Data Product
// ============================================================

export const DEMO_PRODUCT = {
  id: "dp-romi-001",
  name: "ROMI Data Product",
  owner: "Jennifer Moss",
  owner_title: "VP Marketing Operations",
} as const;

export function getStepConfig(step: StepNumber): StepConfig {
  return STEPS.find((s) => s.step === step)!;
}

export function getGateConfig(step: StepNumber): GateConfig | undefined {
  return GATES.find((g) => g.step === step);
}
