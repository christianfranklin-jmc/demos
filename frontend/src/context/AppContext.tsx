import React, { createContext, useContext, useEffect, useReducer, type ReactNode } from "react";
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
  SourceConnection,
  DemoModeState,
  MemoryStatus,
} from "../lib/types";
import { DEMO_PRODUCT } from "../lib/constants";
import { createEmptyPRD } from "../lib/scoring";
import { getOrMintSessionId } from "../lib/session";

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
  // 001-dsa-agent-integration additions
  sessionId: string;                  // Per-tab UUID; populated on mount via useEffect.
  connection: SourceConnection | null; // Request-scoped DB connection; never persisted.
  demoMode: DemoModeState;             // Frontend-only fallback switch (ADR-015 D13).
  memoryStatus: MemoryStatus;          // FR-030 banner driver.
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
  | { type: "LOAD_STATE"; state: Partial<AppState> }
  // 001-dsa-agent-integration additions
  | { type: "SESSION_ID_SET"; sessionId: string }
  | { type: "CONNECTION_SET"; connection: SourceConnection }
  | { type: "CONNECTION_CLEAR" }
  | { type: "DEMO_MODE_ENABLE" }
  | { type: "DEMO_MODE_DISABLE" }
  | { type: "DEMO_MODE_AUTO_ENABLE" }
  | { type: "MEMORY_STATUS_SET"; status: MemoryStatus }
  | { type: "WORKFLOW_INVALIDATE_DOWNSTREAM"; fromStep: StepNumber };

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
  sessionId: "",  // populated by AppProvider's useEffect
  connection: null,
  demoMode: {
    enabled: false,
    reason: null,
    activatedAt: null,
  },
  memoryStatus: "healthy",
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

    case "SESSION_ID_SET":
      return { ...state, sessionId: action.sessionId };

    case "CONNECTION_SET":
      return { ...state, connection: action.connection };

    case "CONNECTION_CLEAR":
      return { ...state, connection: null };

    case "DEMO_MODE_ENABLE":
      return {
        ...state,
        demoMode: { enabled: true, reason: "user_toggle", activatedAt: new Date().toISOString() },
      };

    case "DEMO_MODE_DISABLE":
      return {
        ...state,
        demoMode: { enabled: false, reason: null, activatedAt: null },
      };

    case "DEMO_MODE_AUTO_ENABLE":
      return {
        ...state,
        demoMode: { enabled: true, reason: "auto_fallback", activatedAt: new Date().toISOString() },
      };

    case "MEMORY_STATUS_SET":
      return { ...state, memoryStatus: action.status };

    case "WORKFLOW_INVALIDATE_DOWNSTREAM": {
      // FR-010: clear every step strictly AFTER fromStep. The fromStep itself
      // and every earlier step are preserved.
      const nextStatuses = { ...state.lifecycle.step_statuses };
      const nextApproved = state.lifecycle.approved_steps.filter((s) => s <= action.fromStep);
      for (const s of [1, 2, 3, 4] as StepNumber[]) {
        if (s > action.fromStep) {
          nextStatuses[s] = "not_started";
        }
      }
      return {
        ...state,
        lifecycle: {
          ...state.lifecycle,
          step_statuses: nextStatuses,
          approved_steps: nextApproved,
          current_step: action.fromStep,
          last_updated_at: new Date().toISOString(),
        },
        artifacts: {
          ...state.artifacts,
          conceptual: action.fromStep < 2 ? null : state.artifacts.conceptual,
          logical: action.fromStep < 3 ? null : state.artifacts.logical,
          detailed: action.fromStep < 4 ? null : state.artifacts.detailed,
        },
      };
    }

    default:
      return state;
  }
}

// ─── Context ───

export type AppDispatch = React.Dispatch<AppAction>;

interface AppContextType {
  state: AppState;
  dispatch: AppDispatch;
}

const AppContext = createContext<AppContextType | null>(null);

export function AppProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(appReducer, initialState);

  // Mint-or-restore the per-tab session ID exactly once. sessionStorage
  // survives refreshes within this tab; new tabs get a fresh ID.
  useEffect(() => {
    if (!state.sessionId) {
      dispatch({ type: "SESSION_ID_SET", sessionId: getOrMintSessionId() });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return <AppContext.Provider value={{ state, dispatch }}>{children}</AppContext.Provider>;
}

export function useAppState(): AppContextType {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error("useAppState must be used within AppProvider");
  return ctx;
}
