// SourceChips — per-source row chips on cross-source TTYD responses
// (T098, US4 / FR-017).

import { useTheme } from "../../context/ThemeContext";

export interface SourceChipData {
  connection_id: string;
  driver_type: string;
  scope: string;
  rows: number;
  truncated_at_cap: boolean;
  view_name: string;
  chip_label: string;
}

interface Props {
  chips: SourceChipData[];
  joinRows?: number;
  joinTruncated?: boolean;
}

export default function SourceChips({ chips, joinRows, joinTruncated }: Props) {
  const { theme } = useTheme();
  if (!chips.length) return null;
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {chips.map((c) => (
        <span
          key={c.view_name}
          data-testid="source-chip"
          data-connection-id={c.connection_id}
          className="text-[11px] px-2 py-0.5 rounded-full"
          style={{
            backgroundColor: theme.colors.surfaceSubtle,
            border: `1px solid ${theme.colors.borderSubtle}`,
            color: c.truncated_at_cap
              ? "var(--status-error, #DC2626)"
              : theme.colors.textSecondary,
          }}
          title={c.chip_label}
        >
          {c.chip_label}
        </span>
      ))}
      {joinRows != null ? (
        <span
          data-testid="join-chip"
          className="text-[11px] px-2 py-0.5 rounded-full"
          style={{
            backgroundColor: "var(--status-success, #16A34A)20",
            border: `1px solid var(--status-success, #16A34A)55`,
            color: theme.colors.textPrimary,
          }}
          title={`DuckDB join produced ${joinRows} row(s)`}
        >
          🦆 DuckDB join · {joinRows} rows
          {joinTruncated ? " (capped)" : ""}
        </span>
      ) : null}
    </div>
  );
}
