// ProcessCard — one detected business process (T059, US2).
//
// Renders FR-009: process name + domain icon + source backings + volume
// signal (row count + dollar total where available) + last-activity
// timestamp + sparkline.

import { useTheme } from "../../context/ThemeContext";
import type { BusinessProcess } from "../../hooks/useWorkspaceDiscover";
import type { WorkspaceConnectionRef } from "../../context/AppContext";

interface Props {
  process: BusinessProcess;
  connections: WorkspaceConnectionRef[];
}

const DOMAIN_ICON: Record<BusinessProcess["domain"], string> = {
  wealth_mgmt: "📈",
  accounting: "🧾",
  crm: "👥",
  hr: "🧑‍💼",
  planning: "🎯",
  unspecified: "📁",
};

const DRIVER_ICON: Record<string, string> = {
  postgresql: "🐘",
  redshift: "🔴",
  snowflake: "❄",
  databricks: "🧱",
  iceberg: "🧊",
};

function formatVolume(rows: number, dollar: string | null): string {
  if (dollar) {
    return `${rows.toLocaleString()} rows · ${dollar}`;
  }
  return `${rows.toLocaleString()} rows`;
}

function formatRelative(iso: string | null): string {
  if (!iso) return "—";
  const ts = new Date(iso).getTime();
  if (!Number.isFinite(ts)) return "—";
  const delta = Date.now() - ts;
  if (delta < 60_000) return "just now";
  const mins = Math.round(delta / 60_000);
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.round(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.round(hrs / 24);
  return `${days}d ago`;
}

function Sparkline({ data }: { data: number[] }) {
  const { theme } = useTheme();
  if (!data.length) return null;
  const max = Math.max(...data, 1);
  const width = 72;
  const height = 20;
  const stride = width / Math.max(1, data.length - 1);
  const pts = data
    .map((v, i) => `${(i * stride).toFixed(1)},${(height - (v / max) * height).toFixed(1)}`)
    .join(" ");
  return (
    <svg width={width} height={height} aria-hidden>
      <polyline
        fill="none"
        stroke={theme.colors.accent}
        strokeWidth={1.5}
        points={pts}
      />
    </svg>
  );
}

export default function ProcessCard({ process, connections }: Props) {
  const { theme } = useTheme();
  const sourceConn = connections.find((c) => c.connection_id === process.connection_id);
  const driver = sourceConn?.driver_type ?? "unknown";

  return (
    <div
      className="flex flex-col gap-2 p-4 rounded-lg"
      style={{
        backgroundColor: theme.colors.surfaceSubtle,
        border: `1px solid ${theme.colors.borderSubtle}`,
      }}
      data-testid="process-card"
      data-process-name={process.name}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <span aria-hidden className="text-lg shrink-0">
            {DOMAIN_ICON[process.domain]}
          </span>
          <div className="min-w-0">
            <div
              className="font-semibold truncate"
              style={{ color: theme.colors.textPrimary }}
              title={process.name}
            >
              {process.name}
            </div>
            <div
              className="text-xs flex items-center gap-1"
              style={{ color: theme.colors.textTertiary }}
            >
              <span aria-hidden>{DRIVER_ICON[driver] ?? "•"}</span>
              <span className="truncate">{sourceConn?.display_name ?? driver}</span>
            </div>
          </div>
        </div>
        <Sparkline data={process.sparkline} />
      </div>

      <div
        className="text-sm tabular-nums"
        style={{ color: theme.colors.textSecondary }}
      >
        {formatVolume(process.volume_signal.row_count, process.volume_signal.dollar_total)}
      </div>

      <div
        className="flex items-center justify-between text-xs"
        style={{ color: theme.colors.textTertiary }}
      >
        <span>{process.backing_tables.length} table(s)</span>
        <span>last activity: {formatRelative(process.last_activity_ts)}</span>
      </div>
    </div>
  );
}
