// PillRow — pilled PRD chips (T061, US2).
//
// Renders FR-013: each pill chip = title + subtitle + icon + estimated
// build minutes; clicking a pill emits the chosen pill_id to the parent
// (Step1Discovery), which fetches the PRD draft and navigates to Step 2.

import { useTheme } from "../../context/ThemeContext";
import type { PillSuggestion } from "../../hooks/usePills";

interface Props {
  pills: PillSuggestion[];
  onSelect: (pill: PillSuggestion) => void;
  isSelecting?: string | null; // pill_id currently being drafted
}

export default function PillRow({ pills, onSelect, isSelecting }: Props) {
  const { theme } = useTheme();
  if (!pills.length) {
    return (
      <div
        className="text-xs px-3 py-2 rounded"
        style={{
          color: theme.colors.textTertiary,
          backgroundColor: theme.colors.surfaceSubtle,
          border: `1px solid ${theme.colors.borderSubtle}`,
        }}
        data-testid="pills-empty"
      >
        No pills yet — connect both source warehouses to surface cross-source
        product suggestions.
      </div>
    );
  }
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
      {pills.map((p) => (
        <PillChip
          key={p.pill_id}
          pill={p}
          onSelect={onSelect}
          loading={isSelecting === p.pill_id}
        />
      ))}
    </div>
  );
}

interface ChipProps {
  pill: PillSuggestion;
  onSelect: (pill: PillSuggestion) => void;
  loading: boolean;
}

function PillChip({ pill, onSelect, loading }: ChipProps) {
  const { theme } = useTheme();
  return (
    <button
      type="button"
      data-testid="pill-chip"
      data-pill-id={pill.pill_id}
      onClick={() => onSelect(pill)}
      disabled={loading}
      className="flex flex-col gap-2 p-4 rounded-lg text-left transition-transform hover:scale-[1.01] active:scale-100"
      style={{
        backgroundColor: theme.colors.surfaceSubtle,
        border: `1px solid ${theme.colors.borderSubtle}`,
        cursor: loading ? "wait" : "pointer",
        opacity: loading ? 0.7 : 1,
      }}
    >
      <div className="flex items-center justify-between gap-2">
        <span
          className="font-semibold truncate"
          style={{ color: theme.colors.textPrimary }}
        >
          {pill.title}
        </span>
        <span
          className="text-xs px-2 py-0.5 rounded shrink-0"
          style={{
            color: theme.colors.accent,
            border: `1px solid ${theme.colors.accent}33`,
          }}
        >
          ~{pill.estimated_build_minutes} min
        </span>
      </div>
      <span
        className="text-xs truncate"
        style={{ color: theme.colors.textSecondary }}
        title={pill.subtitle}
      >
        {pill.subtitle}
      </span>
      <span
        className="text-[11px] tabular-nums truncate"
        style={{ color: theme.colors.textTertiary }}
        title={pill.target_iceberg_table}
      >
        → {pill.target_iceberg_table}
      </span>
      {loading ? (
        <span
          className="text-xs"
          style={{ color: theme.colors.textTertiary }}
        >
          Drafting PRD…
        </span>
      ) : null}
    </button>
  );
}
