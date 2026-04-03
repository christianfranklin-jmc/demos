import { useAppState } from "../../context/AppContext";
import { useTheme } from "../../context/ThemeContext";
import FlagBadge from "./FlagBadge";
import EmptyState from "../shared/EmptyState";

interface LogicalModelProps {
  activeTab: string;
}

export default function LogicalModel({ activeTab }: LogicalModelProps) {
  const { state } = useAppState();
  const { theme } = useTheme();
  const model = state.artifacts.logical;

  if (!model || model.entities.length === 0) {
    return <EmptyState stepNumber={3} tabName={activeTab === "Flags" ? "Flags" : "Logical Model"} />;
  }

  if (activeTab === "Flags") {
    const flags = model.flags || [];
    if (flags.length === 0) {
      return <EmptyState stepNumber={3} tabName="Flags" />;
    }
    return (
      <div className="flex-1 overflow-y-auto px-4 py-4">
        <h3
          className="text-xs font-semibold uppercase tracking-wider mb-3"
          style={{ color: theme.colors.textSecondary }}
        >
          Quality Flags ({flags.filter((f) => f.status === "open").length} open)
        </h3>
        <div className="flex flex-col gap-2">
          {flags.map((flag) => (
            <div
              key={flag.flag_id}
              className="px-3 py-3 rounded-lg border"
              style={{
                borderColor: theme.colors.borderSubtle,
                backgroundColor: flag.status === "open" ? theme.colors.white : theme.colors.surfaceSubtle,
              }}
            >
              <div className="flex items-center gap-2 mb-1">
                <FlagBadge type={flag.flag_type} status={flag.status} />
                <span className="text-xs" style={{ color: theme.colors.textTertiary }}>
                  Step {flag.step}
                </span>
              </div>
              <p className="text-sm" style={{ color: theme.colors.textPrimary }}>
                {flag.description}
              </p>
              {flag.resolution && (
                <p className="text-xs mt-1 italic" style={{ color: theme.colors.textTertiary }}>
                  Resolution: {flag.resolution}
                </p>
              )}
            </div>
          ))}
        </div>
      </div>
    );
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
                    style={{ borderBottom: `1px solid ${theme.colors.borderSubtle}` }}
                  >
                    <td className="px-3 py-2 font-mono text-xs" style={{ color: theme.colors.textPrimary }}>
                      {attr.target_field}
                    </td>
                    <td className="px-3 py-2 text-xs" style={{ color: theme.colors.textSecondary }}>
                      {attr.data_type}
                    </td>
                    <td className="px-3 py-2 font-mono text-xs" style={{ color: theme.colors.textTertiary }}>
                      {attr.source_field || "—"}
                    </td>
                    <td className="px-3 py-2 text-xs" style={{ color: theme.colors.textSecondary }}>
                      {attr.transformation_rule || "—"}
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
