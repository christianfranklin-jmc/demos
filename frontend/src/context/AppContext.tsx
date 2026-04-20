import React, { createContext, useContext, useReducer, type ReactNode } from "react";
import type {
  StepNumber,
  StepStatus,
  LifecycleState,
  ConversationMessage,
  PRDArtifact,
  ConceptualModelArtifact,
  LogicalModelArtifact,
  DetailedRequirementsArtifact,
  QualityFlag,
} from "../lib/types";
import { DEMO_PRODUCT } from "../lib/constants";
import { createEmptyPRD } from "../lib/scoring";

// ─── State Shape ───

interface AppState {
  lifecycle: LifecycleState;
  conversation: ConversationMessage[];
  artifacts: {
    prd: PRDArtifact;
    conceptual: ConceptualModelArtifact | null;
    logical: LogicalModelArtifact | null;
    detailed: DetailedRequirementsArtifact | null;
  };
  flags: QualityFlag[];
  ui: {
    isAgentThinking: boolean;
    gateActive: boolean;
    activeArtifactTab: string;
  };
}

// ─── Actions ───

type AppAction =
  | { type: "SET_STEP"; step: StepNumber }
  | { type: "SET_STEP_STATUS"; step: StepNumber; status: StepStatus }
  | { type: "ADD_MESSAGE"; message: ConversationMessage }
  | { type: "UPDATE_PRD"; updates: Partial<PRDArtifact> }
  | { type: "SET_CONCEPTUAL_MODEL"; model: ConceptualModelArtifact }
  | { type: "SET_LOGICAL_MODEL"; model: LogicalModelArtifact }
  | { type: "SET_DETAILED_REQUIREMENTS"; model: DetailedRequirementsArtifact }
  // Granular artifact updates
  | { type: "UPDATE_ENTITY"; entityId: string; updates: Partial<import("../lib/types").ConceptualEntity> }
  | { type: "UPDATE_RELATIONSHIP"; index: number; updates: Partial<import("../lib/types").EntityRelationship> }
  | { type: "UPDATE_LOGICAL_ATTRIBUTE"; entityName: string; attrIndex: number; updates: Partial<import("../lib/types").LogicalAttribute> }
  | { type: "UPDATE_DETAILED_FIELD"; tableName: string; fieldIndex: number; updates: Partial<import("../lib/types").DetailedField> }
  | { type: "ADD_FLAG"; flag: QualityFlag }
  | { type: "RESOLVE_FLAG"; flagId: string; resolution: string; resolvedBy: string }
  | { type: "SET_AGENT_THINKING"; thinking: boolean }
  | { type: "SET_GATE_ACTIVE"; active: boolean }
  | { type: "SET_ACTIVE_TAB"; tab: string }
  | { type: "APPROVE_GATE"; step: StepNumber; approvedBy: string }
  | { type: "LOAD_STATE"; state: Partial<AppState> };

// ─── Initial State ───

const initialState: AppState = {
  lifecycle: {
    data_product_id: DEMO_PRODUCT.id,
    data_product_name: DEMO_PRODUCT.name,
    current_step: 1,
    step_statuses: {
      0: "skipped",
      1: "in_progress",
      2: "not_started",
      3: "not_started",
      4: "not_started",
    },
    last_agent_question: "",
    open_flag_count: 0,
    approved_steps: [],
    last_updated_by: "",
    last_updated_at: new Date().toISOString(),
  },
  conversation: [],
  artifacts: {
    prd: createEmptyPRD(),
    conceptual: null,
    logical: null,
    detailed: null,
  },
  flags: [],
  ui: {
    isAgentThinking: false,
    gateActive: false,
    activeArtifactTab: "PRD Draft",
  },
};

// ─── Reducer ───

function appReducer(state: AppState, action: AppAction): AppState {
  switch (action.type) {
    case "SET_STEP":
      return {
        ...state,
        lifecycle: { ...state.lifecycle, current_step: action.step, last_updated_at: new Date().toISOString() },
      };

    case "SET_STEP_STATUS":
      return {
        ...state,
        lifecycle: {
          ...state.lifecycle,
          step_statuses: { ...state.lifecycle.step_statuses, [action.step]: action.status },
          last_updated_at: new Date().toISOString(),
        },
      };

    case "ADD_MESSAGE":
      return {
        ...state,
        conversation: [...state.conversation, action.message],
        lifecycle: {
          ...state.lifecycle,
          last_agent_question: action.message.message_role === "agent" ? action.message.message_text : state.lifecycle.last_agent_question,
        },
      };

    case "UPDATE_PRD":
      return {
        ...state,
        artifacts: {
          ...state.artifacts,
          prd: { ...state.artifacts.prd, ...action.updates },
        },
      };

    case "SET_CONCEPTUAL_MODEL":
      return { ...state, artifacts: { ...state.artifacts, conceptual: action.model } };

    case "SET_LOGICAL_MODEL":
      return { ...state, artifacts: { ...state.artifacts, logical: action.model } };

    case "SET_DETAILED_REQUIREMENTS":
      return { ...state, artifacts: { ...state.artifacts, detailed: action.model } };

    case "UPDATE_ENTITY": {
      if (!state.artifacts.conceptual) return state;
      return {
        ...state,
        artifacts: {
          ...state.artifacts,
          conceptual: {
            ...state.artifacts.conceptual,
            entities: state.artifacts.conceptual.entities.map((e) =>
              e.entity_id === action.entityId ? { ...e, ...action.updates } : e
            ),
          },
        },
      };
    }

    case "UPDATE_RELATIONSHIP": {
      if (!state.artifacts.conceptual) return state;
      return {
        ...state,
        artifacts: {
          ...state.artifacts,
          conceptual: {
            ...state.artifacts.conceptual,
            relationships: state.artifacts.conceptual.relationships.map((r, i) =>
              i === action.index ? { ...r, ...action.updates } : r
            ),
          },
        },
      };
    }

    case "UPDATE_LOGICAL_ATTRIBUTE": {
      if (!state.artifacts.logical) return state;
      return {
        ...state,
        artifacts: {
          ...state.artifacts,
          logical: {
            ...state.artifacts.logical,
            entities: state.artifacts.logical.entities.map((e) =>
              e.entity_name === action.entityName
                ? {
                    ...e,
                    attributes: e.attributes.map((a, i) =>
                      i === action.attrIndex ? { ...a, ...action.updates } : a
                    ),
                  }
                : e
            ),
          },
        },
      };
    }

    case "UPDATE_DETAILED_FIELD": {
      if (!state.artifacts.detailed) return state;
      const updateFields = (fields: any[]) =>
        fields.map((f: any, i: number) => (i === action.fieldIndex ? { ...f, ...action.updates } : f));

      if (state.artifacts.detailed.fact_table?.table_name === action.tableName) {
        return {
          ...state,
          artifacts: {
            ...state.artifacts,
            detailed: {
              ...state.artifacts.detailed,
              fact_table: {
                ...state.artifacts.detailed.fact_table,
                fields: updateFields(state.artifacts.detailed.fact_table.fields),
              },
            },
          },
        };
      }
      return {
        ...state,
        artifacts: {
          ...state.artifacts,
          detailed: {
            ...state.artifacts.detailed,
            dimension_tables: (state.artifacts.detailed.dimension_tables || []).map((dt) =>
              dt.table_name === action.tableName
                ? { ...dt, fields: updateFields(dt.fields) }
                : dt
            ),
          },
        },
      };
    }

    case "ADD_FLAG":
      return {
        ...state,
        flags: [...state.flags, action.flag],
        lifecycle: { ...state.lifecycle, open_flag_count: state.lifecycle.open_flag_count + 1 },
      };

    case "RESOLVE_FLAG":
      return {
        ...state,
        flags: state.flags.map((f) =>
          f.flag_id === action.flagId
            ? { ...f, status: "resolved" as const, resolution: action.resolution, resolved_by: action.resolvedBy, resolved_at: new Date().toISOString() }
            : f
        ),
        lifecycle: { ...state.lifecycle, open_flag_count: Math.max(0, state.lifecycle.open_flag_count - 1) },
      };

    case "SET_AGENT_THINKING":
      return { ...state, ui: { ...state.ui, isAgentThinking: action.thinking } };

    case "SET_GATE_ACTIVE":
      return { ...state, ui: { ...state.ui, gateActive: action.active } };

    case "SET_ACTIVE_TAB":
      return { ...state, ui: { ...state.ui, activeArtifactTab: action.tab } };

    case "APPROVE_GATE": {
      const nextStep = (action.step + 1) as StepNumber;
      return {
        ...state,
        lifecycle: {
          ...state.lifecycle,
          step_statuses: {
            ...state.lifecycle.step_statuses,
            [action.step]: "approved",
            ...(nextStep <= 4 ? { [nextStep]: "in_progress" } : {}),
          },
          current_step: nextStep <= 4 ? nextStep : action.step,
          approved_steps: [...state.lifecycle.approved_steps, action.step],
          last_updated_by: action.approvedBy,
          last_updated_at: new Date().toISOString(),
        },
        ui: { ...state.ui, gateActive: false },
      };
    }

    case "LOAD_STATE":
      return { ...state, ...action.state };

    default:
      return state;
  }
}

// ─── Context ───

interface AppContextType {
  state: AppState;
  dispatch: React.Dispatch<AppAction>;
}

const AppContext = createContext<AppContextType | null>(null);

export function AppProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(appReducer, initialState);
  return <AppContext.Provider value={{ state, dispatch }}>{children}</AppContext.Provider>;
}

export function useAppState(): AppContextType {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error("useAppState must be used within AppProvider");
  return ctx;
}
