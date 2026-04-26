// ConnectionCard — single-connection card with status pulse + KPI tile (T040, US1).
//
// Shows driver label, schema/db count, table count, last-synced timestamp,
// live/error status pulse, and per-source KPI tiles
// (rows scanned, tables profiled, processes detected) per FR-003.

import { useTheme } from "../../context/ThemeContext";
import type {
  Connection,
  ConnectionStatus,
  DriverType,
} from "../../hooks/useWorkspace";

interface Props {
  connection: Connection;
  onRetry: (connection_id: string) => void;
  onRemove: (connection_id: string) => void;
}

const DRIVER_LABEL: Record<DriverType, string> = {
  postgresql: "PostgreSQL",
  redshift: "Redshift",
  snowflake: "Snowflake",
  databricks: "Databricks",
  iceberg: "Iceberg / Glue",
};

const DRIVER_ICON: Record<DriverType, string> = {
  postgresql: "🐘",
  redshift: "🔴",
  snowflake: "❄",
  databricks: "🧱",
  iceberg: "🧊",
};

const STATUS_COPY: Record<ConnectionStatus, string> = {
  connecting: "Connecting…",
  scanning: "Scanning metadata…",
  live: "Live",
  error: "Error",
};

// Status color tokens — see ADR-020 D4 + research.md R10. T089 will move
// these to CSS custom properties (--status-success, --status-error) in Phase 5;
// inlined here so US1 is self-contained without touching the theme system.
const STATUS_SUCCESS = "#16A34A";
const STATUS_ERROR = "#DC2626";

function statusColor(theme: { colors: Record<string, string> }, s: ConnectionStatus): string {
  switch (s) {
    case "live":
      return STATUS_SUCCESS;
    case "error":
      return STATUS_ERROR;
    case "connecting":
    case "scanning":
    default:
      return theme.colors.accent;
  }
}

function formatRelative(iso: string | null): string {
  if (!iso) return "—";
  const ts = new Date(iso).getTime();
  if (!Number.isFinite(ts)) return "—";
  const delta = Date.now() - ts;
  if (delta < 60_000) return "just now";
  const mins = Math.round(delta / 60_000);
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.round(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  return new Date(iso).toLocaleDateString();
}

function StatusPulse({ status }: { status: ConnectionStatus }) {
  const { theme } = useTheme();
  const color = statusColor(theme, status);
  const isAnimating = status === "connecting" || status === "scanning";
  return (
    <span
      data-testid="status-pulse"
      data-status={status}
      className={`inline-block w-2.5 h-2.5 rounded-full ${
        isAnimating ? "animate-pulse" : ""
      }`}
      style={{ backgroundColor: color }}
    />
  );
}

export default function ConnectionCard({ connection, onRetry, onRemove }: Props) {
  const { theme } = useTheme();
  const { status, error, kpis } = connection;
  return (
    <div
      className="flex flex-col gap-3 p-4 rounded-lg"
      style={{
        backgroundColor: theme.colors.surfaceSubtle,
        border: `1px solid ${theme.colors.borderSubtle}`,
      }}
      data-testid="connection-card"
      data-connection-id={connection.connection_id}
      data-status={status}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2 min-w-0">
          <span aria-hidden className="text-lg">
            {DRIVER_ICON[connection.driver_type]}
          </span>
          <div className="min-w-0">
            <div
              className="font-semibold truncate"
              style={{ color: theme.colors.textPrimary }}
              title={connection.display_name}
            >
              {connection.display_name}
            </div>
            <div
              className="text-xs truncate"
              style={{ color: theme.colors.textTertiary }}
              title={`${DRIVER_LABEL[connection.driver_type]} · ${connection.scope}`}
            >
              {DRIVER_LABEL[connection.driver_type]} · {connection.scope}
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <StatusPulse status={status} />
          <span className="text-xs" style={{ color: theme.colors.textSecondary }}>
            {STATUS_COPY[status]}
          </span>
        </div>
      </div>

      {error ? (
        <div
          className="text-xs px-3 py-2 rounded"
          style={{
            color: STATUS_ERROR,
            backgroundColor: `${STATUS_ERROR}14`,
          }}
        >
          {error.message}
        </div>
      ) : null}

      <div className="grid grid-cols-3 gap-2">
        <KPI label="Tables" value={kpis.tables_total} />
        <KPI label="Rows" value={kpis.rows_estimated} />
        <KPI label="Processes" value={kpis.processes_detected} />
      </div>

      <div className="flex items-center justify-between text-xs">
        <span style={{ color: theme.colors.textTertiary }}>
          Last synced {formatRelative(connection.last_synced_at)}
        </span>
        <div className="flex items-center gap-2">
          {error?.retryable ? (
            <button
              type="button"
              className="px-2 py-1 rounded"
              style={{
                color: theme.colors.accent,
                border: `1px solid ${theme.colors.borderSubtle}`,
              }}
              onClick={() => onRetry(connection.connection_id)}
            >
              Retry
            </button>
          ) : null}
          <button
            type="button"
            className="px-2 py-1 rounded"
            style={{
              color: theme.colors.textSecondary,
              border: `1px solid ${theme.colors.borderSubtle}`,
            }}
            onClick={() => onRemove(connection.connection_id)}
          >
            Remove
          </button>
        </div>
      </div>
    </div>
  );
}

function KPI({ label, value }: { label: string; value: number }) {
  const { theme } = useTheme();
  return (
    <div
      className="flex flex-col px-2 py-1.5 rounded"
      style={{ backgroundColor: theme.colors.white }}
    >
      <span className="text-[10px] uppercase tracking-wide"
            style={{ color: theme.colors.textTertiary }}>
        {label}
      </span>
      <span
        className="text-sm font-semibold tabular-nums"
        style={{ color: theme.colors.textPrimary }}
      >
        {value.toLocaleString()}
      </span>
    </div>
  );
}
