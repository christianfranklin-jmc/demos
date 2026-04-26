// ActivityStream — running activity log on the Build page (T085, US3).
//
// Renders the activity rows produced by useProvisioningRun: per-agent
// events + validation results + run terminus. Auto-scrolls to the
// newest entry; capped at 200 rows in the source so the DOM stays
// bounded.

import { useEffect, useRef } from "react";
import { useTheme } from "../../context/ThemeContext";
import type { ActivityRow } from "../../hooks/useProvisioningRun";

interface Props {
  rows: ActivityRow[];
}

const LEVEL_DOT: Record<ActivityRow["level"], string> = {
  info: "•",
  success: "✓",
  warn: "!",
  error: "✗",
};

const LEVEL_COLOR_FALLBACK: Record<ActivityRow["level"], string> = {
  info: "var(--theme-text-tertiary, #94A3B8)",
  success: "#16A34A",
  warn: "#F97316",
  error: "#DC2626",
};

function formatTime(iso: string): string {
  const d = new Date(iso);
  const hh = String(d.getHours()).padStart(2, "0");
  const mm = String(d.getMinutes()).padStart(2, "0");
  const ss = String(d.getSeconds()).padStart(2, "0");
  return `${hh}:${mm}:${ss}`;
}

export default function ActivityStream({ rows }: Props) {
  const { theme } = useTheme();
  const ref = useRef<HTMLDivElement>(null);

  // Pin to the latest row whenever the list grows.
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
  }, [rows.length]);

  return (
    <div
      ref={ref}
      data-testid="activity-stream"
      className="flex flex-col gap-1 rounded-lg p-3 overflow-y-auto h-full max-h-[420px] font-mono text-xs"
      style={{
        backgroundColor: theme.colors.surfaceSubtle,
        border: `1px solid ${theme.colors.borderSubtle}`,
        color: theme.colors.textSecondary,
      }}
    >
      {rows.length === 0 ? (
        <span style={{ color: theme.colors.textTertiary }}>
          waiting for events…
        </span>
      ) : null}
      {rows.map((row, i) => (
        <div key={i} className="flex items-start gap-2">
          <span
            aria-hidden
            className="shrink-0 w-3 text-center"
            style={{ color: LEVEL_COLOR_FALLBACK[row.level] }}
          >
            {LEVEL_DOT[row.level]}
          </span>
          <span
            className="shrink-0 tabular-nums"
            style={{ color: theme.colors.textTertiary }}
          >
            {formatTime(row.ts)}
          </span>
          {row.agent_id ? (
            <span
              className="shrink-0 px-1.5 rounded text-[10px] uppercase tracking-wide"
              style={{
                color: theme.colors.accent,
                border: `1px solid ${theme.colors.borderSubtle}`,
              }}
            >
              {row.agent_id}
            </span>
          ) : null}
          <span className="break-words" style={{ color: theme.colors.textPrimary }}>
            {row.message}
          </span>
        </div>
      ))}
    </div>
  );
}
