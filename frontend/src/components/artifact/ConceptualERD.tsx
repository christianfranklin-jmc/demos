import { useCallback } from "react";
import { useAppState } from "../../context/AppContext";
import { useTheme } from "../../context/ThemeContext";
import { validateField, hasExistingFlag } from "../../lib/validation";
import EntityCard from "./EntityCard";
import EditableCell from "./EditableCell";
import EmptyState from "../shared/EmptyState";
import type { StepNumber } from "../../lib/types";

interface ConceptualERDProps {
  activeTab: string;
}

export default function ConceptualERD({ activeTab }: ConceptualERDProps) {
  const { state, dispatch } = useAppState();
  const { theme } = useTheme();
  const model = state.artifacts.conceptual;

  const handleValidate = useCallback(
    (fieldKey: string, value: any) => {
      if (!theme.features.enableStandardsValidation) return;
      const violations = validateField(2 as StepNumber, fieldKey, value, state.lifecycle.data_product_id);
      for (const v of violations) {
        if (!hasExistingFlag(state.flags, 2, v.flag_type)) {
          dispatch({ type: "ADD_FLAG", flag: v });
        }
      }
    },
    [dispatch, state.lifecycle.data_product_id, state.flags, theme.features.enableStandardsValidation]
  );

  if (!model || model.entities.length === 0) {
    return <EmptyState stepNumber={2} tabName="Conceptual Model" />;
  }

  if (activeTab === "Relationships") {
    return (
      <div className="flex-1 overflow-y-auto px-4 py-4">
        <h3
          className="text-xs font-semibold uppercase tracking-wider mb-3"
          style={{ color: theme.colors.textSecondary }}
        >
          Entity Relationships
        </h3>
        <div className="flex flex-col gap-2">
          {model.relationships.map((rel, i) => (
            <div
              key={i}
              className="flex items-center gap-2 px-3 py-2 rounded text-sm"
              style={{
                backgroundColor: theme.colors.surfaceSubtle,
                color: theme.colors.textPrimary,
              }}
            >
              <EditableCell
                value={rel.from_entity}
                mono
                onSave={(v) => dispatch({ type: "UPDATE_RELATIONSHIP", index: i, updates: { from_entity: v } })}
                className="font-medium text-xs"
              />
              <span style={{ color: theme.colors.textTertiary }}>&rarr;</span>
              <EditableCell
                value={rel.verb}
                onSave={(v) => dispatch({ type: "UPDATE_RELATIONSHIP", index: i, updates: { verb: v } })}
                className="text-xs"
              />
              <span style={{ color: theme.colors.textTertiary }}>&rarr;</span>
              <EditableCell
                value={rel.to_entity}
                mono
                onSave={(v) => dispatch({ type: "UPDATE_RELATIONSHIP", index: i, updates: { to_entity: v } })}
                className="font-medium text-xs"
              />
            </div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto px-4 py-4">
      <div className="grid grid-cols-2 gap-3">
        {model.entities.map((entity) => (
          <EntityCard
            key={entity.entity_id}
            entity={entity}
            onUpdate={(updates) =>
              dispatch({ type: "UPDATE_ENTITY", entityId: entity.entity_id, updates })
            }
            onValidate={handleValidate}
          />
        ))}
      </div>
    </div>
  );
}
