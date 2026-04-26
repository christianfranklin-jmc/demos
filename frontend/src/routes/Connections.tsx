// Connections — multi-source workspace page (T039, US1).
//
// Top-level surface for adding/listing/managing workspace connections.
// Renders WorkspaceKPIStrip + a card grid of ConnectionCards, with an
// "Add Connection" CTA that opens AddConnectionModal. Reachable from
// AppShell via a sidebar entry once US1 is wired into the shell.

import { useState } from "react";
import { useTheme } from "../context/ThemeContext";
import { useWorkspace } from "../hooks/useWorkspace";
import AddConnectionModal from "../components/workspace/AddConnectionModal";
import ConnectionCard from "../components/workspace/ConnectionCard";
import WorkspaceKPIStrip from "../components/workspace/WorkspaceKPIStrip";

export default function Connections() {
  const { connections, kpis, isLoading, error, add, remove, retry } = useWorkspace();
  const { theme } = useTheme();
  const [modalOpen, setModalOpen] = useState(false);

  return (
    <div className="flex flex-col gap-6 p-6">
      <header className="flex items-start justify-between gap-4">
        <div>
          <h1
            className="text-2xl font-semibold"
            style={{ color: theme.colors.textPrimary }}
          >
            Connections
          </h1>
          <p
            className="text-sm mt-1"
            style={{ color: theme.colors.textSecondary }}
          >
            Add data sources to this workspace. Each connection contributes to
            the KPI strip below; closing the tab discards the workspace, but
            each connection's durable state survives and reattaches on re-add.
          </p>
        </div>
        <button
          type="button"
          onClick={() => setModalOpen(true)}
          className="px-3 py-2 rounded font-semibold shrink-0"
          style={{
            color: theme.colors.white,
            backgroundColor: theme.colors.accent,
          }}
        >
          + Add connection
        </button>
      </header>

      <WorkspaceKPIStrip kpis={kpis} />

      {error ? (
        <div
          role="alert"
          className="text-xs px-3 py-2 rounded"
          // Status hex inlined per ADR-020 D4 (status-error token).
          style={{
            color: "#DC2626",
            backgroundColor: "#DC262614",
          }}
        >
          {error}
        </div>
      ) : null}

      {connections.length === 0 ? (
        <EmptyState onAdd={() => setModalOpen(true)} isLoading={isLoading} />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {connections.map((c) => (
            <ConnectionCard
              key={c.connection_id}
              connection={c}
              onRetry={retry}
              onRemove={remove}
            />
          ))}
        </div>
      )}

      <AddConnectionModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        onSubmit={async (input) => {
          const r = await add(input);
          if ("kind" in r && r.kind === "error") {
            return { ok: false, message: r.message };
          }
          return { ok: true };
        }}
      />
    </div>
  );
}

function EmptyState({ onAdd, isLoading }: { onAdd: () => void; isLoading: boolean }) {
  const { theme } = useTheme();
  return (
    <div
      className="flex flex-col items-center justify-center gap-3 py-16 rounded-lg"
      style={{
        backgroundColor: theme.colors.surfaceSubtle,
        border: `1px dashed ${theme.colors.borderSubtle}`,
      }}
      data-testid="connections-empty"
    >
      <span
        className="text-base font-semibold"
        style={{ color: theme.colors.textPrimary }}
      >
        {isLoading ? "Loading workspace…" : "No connections yet"}
      </span>
      <span
        className="text-sm max-w-md text-center"
        style={{ color: theme.colors.textSecondary }}
      >
        Add a PostgreSQL, Snowflake, Redshift, Databricks, or Iceberg/Glue
        connection to start populating this workspace. The Pinnacle showcase
        adds Pinnacle PG + Pinnacle SF.
      </span>
      <button
        type="button"
        onClick={onAdd}
        className="px-3 py-2 rounded"
        style={{
          color: theme.colors.white,
          backgroundColor: theme.colors.accent,
        }}
      >
        Add your first connection
      </button>
    </div>
  );
}
