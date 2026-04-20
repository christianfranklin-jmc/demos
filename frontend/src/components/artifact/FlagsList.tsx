import { useAppState } from "../../context/AppContext";
import { useTheme } from "../../context/ThemeContext";
import FlagBadge from "./FlagBadge";
import EmptyState from "../shared/EmptyState";
import type { QualityFlag } from "../../lib/types";

export default function FlagsList() {
  const { state } = useAppState();
  const { theme } = useTheme();

  const allFlags = state.flags;
  if (allFlags.length === 0) {
    return <EmptyState stepNumber={state.lifecycle.current_step} tabName="Flags" />;
  }

  const qualityFlags = allFlags.filter((f) => !f.flag_type.startsWith("standards_"));
  const standardsFlags = allFlags.filter((f) => f.flag_type.startsWith("standards_"));

  const renderFlag = (flag: QualityFlag) => (
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
        <span
          className="text-xs px-1.5 py-0.5 rounded"
          style={{
            backgroundColor: theme.colors.surfaceInput,
            color: theme.colors.textTertiary,
            fontSize: "10px",
          }}
        >
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
  );

  return (
    <div className="flex-1 overflow-y-auto px-4 py-4">
      {/* Summary */}
      <div className="flex items-center gap-3 mb-4">
        <span className="text-sm font-medium" style={{ color: theme.colors.textPrimary }}>
          {allFlags.filter((f) => f.status === "open").length} open
        </span>
        <span className="text-sm" style={{ color: theme.colors.textTertiary }}>
          &middot; {allFlags.filter((f) => f.status === "resolved").length} resolved
        </span>
        <span className="text-sm" style={{ color: theme.colors.textTertiary }}>
          &middot; {allFlags.filter((f) => f.status === "deferred").length} deferred
        </span>
      </div>

      {/* Quality Flags Section */}
      {qualityFlags.length > 0 && (
        <div className="mb-5">
          <h3
            className="text-xs font-semibold uppercase tracking-wider mb-2"
            style={{ color: theme.colors.textSecondary }}
          >
            Quality Flags ({qualityFlags.filter((f) => f.status === "open").length} open)
          </h3>
          <div className="flex flex-col gap-2">
            {qualityFlags.map(renderFlag)}
          </div>
        </div>
      )}

      {/* Standards Violations Section */}
      {standardsFlags.length > 0 && (
        <div className="mb-5">
          <h3
            className="text-xs font-semibold uppercase tracking-wider mb-2"
            style={{ color: theme.colors.flagPurple || "#8B5CF6" }}
          >
            Standards Violations ({standardsFlags.filter((f) => f.status === "open").length} open)
          </h3>
          <div className="flex flex-col gap-2">
            {standardsFlags.map(renderFlag)}
          </div>
        </div>
      )}
    </div>
  );
}
