// WorkspaceKPIStrip — animated KPI tiles across live connections (T042, US1).
//
// Renders the workspace-wide totals exposed by GET /workspace/kpis.
// Counters animate from their previous value to the new value whenever
// the underlying numbers change, satisfying FR-004 ("animate as
// connections come online").

import { useEffect, useMemo, useRef, useState } from "react";
import { useTheme } from "../../context/ThemeContext";
import type { WorkspaceKPIs } from "../../hooks/useWorkspace";

interface Props {
  kpis: WorkspaceKPIs | null;
}

interface Tile {
  label: string;
  value: number;
  hint?: string;
}

const ANIM_MS = 600;

function easeOutCubic(t: number): number {
  return 1 - Math.pow(1 - t, 3);
}

/** Animate from `from` to `to` over `duration` ms; returns the latest value. */
function useAnimatedNumber(target: number, duration = ANIM_MS): number {
  const [value, setValue] = useState(target);
  const fromRef = useRef(target);
  const startRef = useRef<number | null>(null);

  useEffect(() => {
    if (target === value) return;
    fromRef.current = value;
    startRef.current = null;
    let raf = 0;
    const step = (ts: number) => {
      if (startRef.current === null) startRef.current = ts;
      const elapsed = ts - startRef.current;
      const t = Math.min(1, elapsed / duration);
      const next = Math.round(
        fromRef.current + (target - fromRef.current) * easeOutCubic(t)
      );
      setValue(next);
      if (t < 1) raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [target, duration]);

  return value;
}

function KPITile({ label, value, hint }: Tile) {
  const { theme } = useTheme();
  const animated = useAnimatedNumber(value);
  return (
    <div
      className="flex flex-col gap-1 px-4 py-3 rounded-lg"
      style={{
        backgroundColor: theme.colors.surfaceSubtle,
        border: `1px solid ${theme.colors.borderSubtle}`,
      }}
    >
      <span
        className="text-xs uppercase tracking-wide"
        style={{ color: theme.colors.textTertiary }}
      >
        {label}
      </span>
      <span
        className="text-2xl font-semibold tabular-nums"
        style={{ color: theme.colors.textPrimary }}
      >
        {animated.toLocaleString()}
      </span>
      {hint ? (
        <span className="text-xs" style={{ color: theme.colors.textTertiary }}>
          {hint}
        </span>
      ) : null}
    </div>
  );
}

export default function WorkspaceKPIStrip({ kpis }: Props) {
  const tiles = useMemo<Tile[]>(
    () => [
      { label: "Sources connected", value: kpis?.sources_connected ?? 0 },
      { label: "Tables", value: kpis?.tables_total ?? 0 },
      { label: "Rows", value: kpis?.rows_total ?? 0, hint: "estimated" },
      { label: "Processes detected", value: kpis?.processes_detected ?? 0 },
      {
        label: "Semantic entities",
        value: kpis?.semantic_entities_total ?? 0,
        hint: "populated by US5",
      },
    ],
    [kpis]
  );

  return (
    <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
      {tiles.map((t) => (
        <KPITile key={t.label} {...t} />
      ))}
    </div>
  );
}
