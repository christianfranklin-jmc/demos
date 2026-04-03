import { useAppState } from "../../context/AppContext";
import { useTheme } from "../../context/ThemeContext";
import CompletenessBar from "./CompletenessBar";
import EmptyState from "../shared/EmptyState";

interface DetailedRequirementsProps {
  activeTab: string;
}

function FieldTable({ title, fields, theme }: { title: string; fields: any[]; theme: any }) {
  if (!fields || fields.length === 0) return null;
  return (
    <div className="mb-6">
      <h3 className="text-sm font-medium mb-2" style={{ color: theme.colors.textPrimary }}>
        {title}
      </h3>
      <div className="overflow-x-auto">
        <table className="w-full text-sm" style={{ borderCollapse: "collapse" }}>
          <thead>
            <tr style={{ borderBottom: `1px solid ${theme.colors.borderSubtle}` }}>
              {["Target Field", "Source", "Source Field", "Transformation", "Required", "Governance", "Phase"].map(
                (h) => (
                  <th
                    key={h}
                    className="text-left text-xs font-medium uppercase tracking-wider px-2 py-2"
                    style={{ color: theme.colors.textSecondary }}
                  >
                    {h}
                  </th>
                )
              )}
            </tr>
          </thead>
          <tbody>
            {fields.map((field: any, i: number) => (
              <tr
                key={i}
                style={{ borderBottom: `1px solid ${theme.colors.borderSubtle}` }}
              >
                <td className="px-2 py-2 font-mono text-xs" style={{ color: theme.colors.textPrimary }}>
                  {field.target_field}
                </td>
                <td className="px-2 py-2 text-xs" style={{ color: theme.colors.textSecondary }}>
                  {field.source_system}
                </td>
                <td className="px-2 py-2 font-mono text-xs" style={{ color: theme.colors.textTertiary }}>
                  {field.source_field}
                </td>
                <td className="px-2 py-2 text-xs max-w-48 truncate" style={{ color: theme.colors.textSecondary }}>
                  {field.transformation || "Direct map"}
                </td>
                <td className="px-2 py-2 text-xs" style={{ color: theme.colors.textPrimary }}>
                  {field.required ? "Y" : "N"}
                </td>
                <td className="px-2 py-2">
                  <GovernanceBadge level={field.governance} theme={theme} />
                </td>
                <td className="px-2 py-2">
                  <PhaseBadge phase={field.phase} theme={theme} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function GovernanceBadge({ level, theme }: { level: string; theme: any }) {
  const colors: Record<string, string> = {
    Public: theme.colors.accent,
    Restricted: theme.colors.flagAmber,
    Masked: "#8B5CF6",
    Excluded: theme.colors.textTertiary,
  };
  return (
    <span
      className="text-xs px-1.5 py-0.5 rounded"
      style={{
        backgroundColor: (colors[level] || theme.colors.textTertiary) + "20",
        color: colors[level] || theme.colors.textTertiary,
        fontSize: "10px",
      }}
    >
      {level}
    </span>
  );
}

function PhaseBadge({ phase, theme }: { phase: string; theme: any }) {
  const isMvp = phase === "MVP";
  return (
    <span
      className="text-xs px-1.5 py-0.5 rounded"
      style={{
        backgroundColor: isMvp ? theme.colors.accent + "20" : theme.colors.surfaceInput,
        color: isMvp ? theme.colors.textPrimary : theme.colors.textTertiary,
        fontSize: "10px",
      }}
    >
      {phase}
    </span>
  );
}

export default function DetailedRequirements({ activeTab }: DetailedRequirementsProps) {
  const { state } = useAppState();
  const { theme } = useTheme();
  const model = state.artifacts.detailed;

  if (!model) {
    return <EmptyState stepNumber={4} tabName={activeTab === "Completeness" ? "Completeness" : "Detailed Requirements"} />;
  }

  if (activeTab === "Completeness") {
    const totalFields =
      (model.fact_table?.fields?.length || 0) +
      (model.dimension_tables?.reduce((a, d) => a + d.fields.length, 0) || 0);
    return (
      <div className="flex-1 overflow-y-auto px-4 py-4">
        <h3
          className="text-xs font-semibold uppercase tracking-wider mb-3"
          style={{ color: theme.colors.textSecondary }}
        >
          Field Mapping Completeness
        </h3>
        <CompletenessBar score={model.completeness_score} />
        <div className="mt-4 text-sm" style={{ color: theme.colors.textSecondary }}>
          <p>{totalFields} fields mapped across {1 + (model.dimension_tables?.length || 0)} tables</p>
          <p className="mt-1">{model.calculated_metrics?.length || 0} calculated metrics defined</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto px-4 py-4">
      <CompletenessBar score={model.completeness_score} />

      {model.fact_table && (
        <FieldTable
          title={`${model.fact_table.table_name} (grain: ${model.fact_table.grain})`}
          fields={model.fact_table.fields}
          theme={theme}
        />
      )}

      {model.dimension_tables?.map((dim) => (
        <FieldTable
          key={dim.table_name}
          title={dim.table_name}
          fields={dim.fields}
          theme={theme}
        />
      ))}

      {model.calculated_metrics && model.calculated_metrics.length > 0 && (
        <div className="mb-6">
          <h3 className="text-sm font-medium mb-2" style={{ color: theme.colors.textPrimary }}>
            Calculated Metrics
          </h3>
          <div className="flex flex-col gap-2">
            {model.calculated_metrics.map((m, i) => (
              <div
                key={i}
                className="px-3 py-2 rounded border"
                style={{ borderColor: theme.colors.borderSubtle }}
              >
                <div className="flex items-center gap-2">
                  <span className="font-mono text-xs" style={{ color: theme.colors.textPrimary }}>
                    {m.field}
                  </span>
                  <GovernanceBadge level={m.governance} theme={theme} />
                  <PhaseBadge phase={m.phase} theme={theme} />
                </div>
                <p className="text-xs mt-1" style={{ color: theme.colors.textSecondary }}>
                  {m.formula}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
