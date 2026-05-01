// TtydKPIBar — small KPI strip above cross-source TTYD responses (T099, US4 / FR-020).

import { useTheme } from "../../context/ThemeContext";

export interface TtydKPISnapshot {
  queries_answered_today: number;
  avg_latency_ms: number;
  sources_used_today: number;
  semantic_hit_rate: number;
}

interface Props {
  snapshot: TtydKPISnapshot | null;
}

export default function TtydKPIBar({ snapshot }: Props) {
  const { theme } = useTheme();
  if (!snapshot) return null;
  const tiles = [
    { label: "Queries", value: snapshot.queries_answered_today.toLocaleString() },
    { label: "Avg latency", value: `${snapshot.avg_latency_ms} ms` },
    { label: "Sources used", value: snapshot.sources_used_today.toLocaleString() },
    {
      label: "Semantic hits",
      value: `${(snapshot.semantic_hit_rate * 100).toFixed(0)}%`,
    },
  ];
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
      {tiles.map((t) => (
        <div
          key={t.label}
          className="px-3 py-2 rounded-md"
          style={{
            backgroundColor: theme.colors.surfaceSubtle,
            border: `1px solid ${theme.colors.borderSubtle}`,
          }}
        >
          <div
            className="text-[10px] uppercase tracking-wide"
            style={{ color: theme.colors.textTertiary }}
          >
            {t.label}
          </div>
          <div
            className="text-sm font-semibold tabular-nums"
            style={{ color: theme.colors.textPrimary }}
          >
            {t.value}
          </div>
        </div>
      ))}
    </div>
  );
}
