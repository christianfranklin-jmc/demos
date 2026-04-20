import { useCallback } from "react";
import { useAppState } from "../../context/AppContext";
import { useTheme } from "../../context/ThemeContext";
import { validateField, hasExistingFlag } from "../../lib/validation";
import FlagBadge from "./FlagBadge";
import EditableCell from "./EditableCell";
import FlagsList from "./FlagsList";
import EmptyState from "../shared/EmptyState";
import type { StepNumber } from "../../lib/types";

interface LogicalModelProps {
  activeTab: string;
}

export default function LogicalModel({ activeTab }: LogicalModelProps) {
  const { state, dispatch } = useAppState();
  const { theme } = useTheme();
  const model = state.artifacts.logical;

  const handleValidate = useCallback(
    (fieldKey: string, value: any) => {
      if (!theme.features.enableStandardsValidation) return;
      const violations = validateField(3 as StepNumber, fieldKey, value, state.lifecycle.data_product_id);
      for (const v of violations) {
        if (!hasExistingFlag(state.flags, 3, v.flag_type)) {
          dispatch({ type: "ADD_FLAG", flag: v });
        }
      }
    },
    [dispatch, state.lifecycle.data_product_id, state.flags, theme.features.enableStandardsValidation]
  );

  if (!model || model.entities.length === 0) {
    return <EmptyState stepNumber={3} tabName={activeTab === "Flags" ? "Flags" : "Logical Model"} />;
  }

  if (activeTab === "Flags") {
    return <FlagsList />;
  }

  return (
    <div className="flex-1 overflow-y-auto px-4 py-4">
      {model.entities.map((entity) => (
        <div key={entity.entity_name} className="mb-6">
          <div className="flex items-center gap-2 mb-2">
            <h3 className="text-sm font-medium" style={{ color: theme.colors.textPrimary }}>
              {entity.entity_name}
            </h3>
            <span
              className="text-xs px-1.5 py-0.5 rounded"
              style={{
                backgroundColor: theme.colors.surfaceInput,
                color: theme.colors.textSecondary,
                fontSize: "10px",
              }}
            >
              {entity.role}
            </span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm" style={{ borderCollapse: "collapse" }}>
              <thead>
                <tr style={{ borderBottom: `1px solid ${theme.colors.borderSubtle}` }}>
                  {["Target Field", "Data Type", "Source Field", "Transformation", "Flag"].map((h) => (
                    <th
                      key={h}
                      className="text-left text-xs font-medium uppercase tracking-wider px-3 py-2"
                      style={{ color: theme.colors.textSecondary }}
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {entity.attributes.map((attr, i) => (
                  <tr
                    key={i}
                    className="group"
                    style={{ borderBottom: `1px solid ${theme.colors.borderSubtle}` }}
                  >
                    <td className="px-3 py-2 text-xs">
                      <EditableCell
                        value={attr.target_field}
                        mono
                        onSave={(v) =>
                          dispatch({
                            type: "UPDATE_LOGICAL_ATTRIBUTE",
                            entityName: entity.entity_name,
                            attrIndex: i,
                            updates: { target_field: v },
                          })
                        }
                        onValidate={(v) => handleValidate("target_field", v)}
                      />
                    </td>
                    <td className="px-3 py-2 text-xs">
                      <EditableCell
                        value={attr.data_type}
                        onSave={(v) =>
                          dispatch({
                            type: "UPDATE_LOGICAL_ATTRIBUTE",
                            entityName: entity.entity_name,
                            attrIndex: i,
                            updates: { data_type: v },
                          })
                        }
                        onValidate={(v) => handleValidate("data_type", v)}
                      />
                    </td>
                    <td className="px-3 py-2 text-xs">
                      <EditableCell
                        value={attr.source_field || ""}
                        mono
                        onSave={(v) =>
                          dispatch({
                            type: "UPDATE_LOGICAL_ATTRIBUTE",
                            entityName: entity.entity_name,
                            attrIndex: i,
                            updates: { source_field: v || null },
                          })
                        }
                        onValidate={(v) => handleValidate("source_field", v)}
                      />
                    </td>
                    <td className="px-3 py-2 text-xs">
                      <EditableCell
                        value={attr.transformation_rule || ""}
                        onSave={(v) =>
                          dispatch({
                            type: "UPDATE_LOGICAL_ATTRIBUTE",
                            entityName: entity.entity_name,
                            attrIndex: i,
                            updates: { transformation_rule: v || null },
                          })
                        }
                      />
                    </td>
                    <td className="px-3 py-2">
                      {attr.flag ? <FlagBadge type={attr.flag} /> : null}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ))}
    </div>
  );
}
