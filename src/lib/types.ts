// ============================================================
// DSA MVP — Type Definitions
// All interfaces match the persistent layer schema (target: Snowflake)
// ============================================================

// --- Lifecycle State (lifecycle_state sheet/table) ---

export type StepNumber = 0 | 1 | 2 | 3 | 4;

export type StepStatus =
  | "not_started"
  | "in_progress"
  | "awaiting_approval"
  | "approved"
  | "skipped"; // Step 0 only

export interface LifecycleState {
  data_product_id: string;
  data_product_name: string;
  current_step: StepNumber;
  step_statuses: Record<StepNumber, StepStatus>;
  last_agent_question: string;
  open_flag_count: number;
  approved_steps: StepNumber[];
  last_updated_by: string;
  last_updated_at: string; // ISO 8601
}

// --- Artifact Log (artifact_log sheet/table) ---

export type ArtifactType =
  | "stakeholder_map"
  | "prd"
  | "conceptual_model"
  | "logical_model"
  | "detailed_requirements";

export interface ArtifactLog {
  artifact_id: string;
  data_product_id: string;
  step: StepNumber;
  artifact_type: ArtifactType;
  content_json: string; // Serialized artifact content
  version: string;
  created_at: string;
}

// --- Approval Audit (approval_audit sheet/table) ---

export type ApprovalAction = "approved" | "changes_requested";

export type ApproverPersona =
  | "data_product_owner"
  | "analytics_engineer"
  | "data_architect";

export interface ApprovalAudit {
  data_product_id: string;
  step: StepNumber;
  artifact_id: string;
  action: ApprovalAction;
  approved_by: string;
  persona: ApproverPersona;
  approved_at: string;
  notes: string;
}

// --- Agent Conversation Log (agent_conversation_log sheet/table) ---

export type MessageRole = "agent" | "user" | "system";

export interface ConversationMessage {
  data_product_id: string;
  step: StepNumber;
  message_role: MessageRole;
  message_text: string;
  timestamp: string;
  // UI-only fields (not persisted):
  suggested_replies?: string[];
  source_context?: SourceContext;
}

// --- Quality Flags (quality_flags sheet/table) ---

export type FlagType =
  | "grain_ambiguity"
  | "access_dependency"
  | "missing_source"
  | "derived_field"
  | "naming_conflict";

export type FlagStatus = "open" | "resolved" | "deferred";

export interface QualityFlag {
  flag_id: string;
  data_product_id: string;
  step: StepNumber;
  flag_type: FlagType;
  description: string;
  status: FlagStatus;
  resolution: string | null;
  resolved_by: string | null;
  resolved_at: string | null;
  created_at: string;
}

// --- PRD Artifact Content (Step 1 output) ---

export interface PRDArtifact {
  business_objective: string | null;
  current_state_pain: string | null;
  decisions_enabled: string[] | null;
  primary_consumers: ConsumerPersona[] | null;
  secondary_consumers: string | null;
  grain_statement: string | null;
  time_range: TimeRange | null;
  key_metrics: MetricDefinition[] | null;
  source_systems: SourceSystem[] | null;
  success_criteria: string | null;
  acceptance_criteria: AcceptanceCriterion[] | null;
  constraints: string | null;
  scope_in: string[] | null;
  scope_out: string[] | null;
  completeness_score: number; // 0-100
}

export interface ConsumerPersona {
  persona: string;
  role: string;
  access_level: string;
}

export interface TimeRange {
  historical_coverage: string;
  refresh_cadence: string;
  snapshot_logic: string;
  fiscal_calendar: string;
}

export interface MetricDefinition {
  name: string;
  definition: string;
  formula: string | null;
  priority: "MVP" | "Phase 2";
}

export interface SourceSystem {
  system: string;
  data_domain: string;
  access_confirmed: boolean | null; // null = TBD
}

export interface AcceptanceCriterion {
  criterion: string;
  test_method: string;
  owner: string;
}

// --- Conceptual Model Artifact (Step 2 output) ---

export type EntityRole = "FACT" | "DIM" | "REF";

export interface ConceptualEntity {
  entity_id: string;
  entity_name: string;
  role: EntityRole;
  description: string;
  abstract_attributes: string[]; // 2-3 high-level descriptions
  cardinality_hint: string | null;
}

export interface EntityRelationship {
  from_entity: string;
  verb: string;
  to_entity: string;
}

export interface ConceptualModelArtifact {
  entities: ConceptualEntity[];
  relationships: EntityRelationship[];
}

// --- Logical Model Artifact (Step 3 output) ---

export type DataType =
  | "INT"
  | "VARCHAR"
  | "DECIMAL"
  | "DATE"
  | "BOOLEAN"
  | "TIMESTAMP";

export interface LogicalAttribute {
  target_field: string;
  data_type: string;
  source_field: string | null;
  transformation_rule: string | null;
  flag: FlagType | null;
}

export interface LogicalEntity {
  entity_name: string;
  role: EntityRole;
  attributes: LogicalAttribute[];
}

export interface LogicalModelArtifact {
  entities: LogicalEntity[];
  flags: QualityFlag[];
}

// --- Detailed Requirements Artifact (Step 4 output) ---

export type GovernanceLevel = "Public" | "Restricted" | "Masked" | "Excluded";
export type PhaseLabel = "MVP" | "Phase 2" | "Out of scope";

export interface DetailedField {
  target_field: string;
  data_type: string;
  source_system: string;
  source_field: string;
  transformation: string;
  business_rule: string;
  required: boolean;
  governance: GovernanceLevel;
  phase: PhaseLabel;
}

export interface DetailedRequirementsArtifact {
  fact_table: {
    table_name: string;
    grain: string;
    fields: DetailedField[];
  };
  dimension_tables: {
    table_name: string;
    fields: DetailedField[];
  }[];
  calculated_metrics: {
    field: string;
    formula: string;
    business_rule: string;
    governance: GovernanceLevel;
    phase: PhaseLabel;
  }[];
  completeness_score: number;
}

// --- Source Context (inline discovery results) ---

export type SourceContextType = "highspot" | "atlan" | "snowflake" | "allocadia";

export interface SourceContext {
  type: SourceContextType;
  title: string;
  summary: string;
  metadata?: Record<string, string>;
  quality_score?: number;
  flags?: string[];
}

// --- Step Configuration ---

export interface StepConfig {
  step: StepNumber;
  name: string;
  agent_persona: string;
  artifact_type: ArtifactType;
  tab_name: string;
  gate_name: string | null;
  approver_persona: ApproverPersona | null;
  system_prompt_path: string;
}

// --- Gate Configuration ---

export interface GateConfig {
  step: StepNumber;
  gate_name: string;
  approver_persona: ApproverPersona;
  approver_description: string;
  hard_block_on_flags: boolean;
  soft_warn_threshold: number; // completeness % below which to warn
}
