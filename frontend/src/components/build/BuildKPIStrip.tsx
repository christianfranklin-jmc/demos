// BuildKPIStrip — provisioning KPI tiles (T084, US3 / FR-030).
//
// Displays the rolling KPI series from the v2 SSE stream:
// rows in motion / agents active / files written / latency p95 /
// estimated cost / ETA. Counters animate from previous → next via
// requestAnimationFrame easing so the demo feels alive.

import { useEffect, useRef, useState } from "react";
import { useTheme } from "../../context/ThemeContext";
import type { KpiTick } from "../../lib/agentcore-client/parsers/v2";

interface Props {
  ticks: KpiTick[];
}

const ANIM_MS = 500;

function easeOutCubic(t: number): number {
  return 1 - Math.pow(1 - t, 3);
}

function useAnimatedNumber(target: number): number {
  const [value, setValue] = useState(target);
  const fromRef = useRef(target);
  useEffect(() => {
    if (target === value) return;
    fromRef.current = value;
    let raf = 0;
    let start: number | null = null;
    const step = (ts: number) => {
      if (start === null) start = ts;
      const elapsed = ts - start;
      const t = Math.min(1, elapsed / ANIM_MS);
      const next = Math.round(
        fromRef.current + (target - fromRef.current) * easeOutCubic(t)
      );
      setValue(next);
      if (t < 1) raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [target]);
  return value;
}

function Tile({
  label,
  value,
  hint,
}: {
  label: string;
  value: number;
  hint?: string;
}) {
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

export default function BuildKPIStrip({ ticks }: Props) {
  const latest = ticks[ticks.length - 1];
  const rows = latest?.rows_in_motion ?? 0;
  const active = latest?.agents_active ?? 0;
  const files = latest?.files_written ?? 0;
  const p95 = latest?.latency_ms_p95 ?? 0;
  const cost =
    latest?.est_cost_usd != null ? Math.round(latest.est_cost_usd * 100) : 0;
  const eta = latest?.eta_seconds ?? 0;

  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
      <Tile label="Rows in motion" value={rows} />
      <Tile label="Agents active" value={active} />
      <Tile label="Files written" value={files} />
      <Tile label="Latency p95" value={p95} hint="ms" />
      <Tile label="Est cost" value={cost} hint="USD ¢" />
      <Tile label="ETA" value={eta} hint="seconds" />
    </div>
  );
}
