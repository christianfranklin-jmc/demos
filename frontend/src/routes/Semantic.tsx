// Semantic — per-connection semantic graph page (T108, US5).
//
// Connection switcher (across the workspace's connections) → graph for
// the selected connection → side panel showing the entity detail when
// a node is clicked. Per Q2: each connection has its own independent
// graph; no cross-connection overlay.

import { useEffect, useMemo, useState } from "react";
import { useTheme } from "../context/ThemeContext";
import { useAppState } from "../context/AppContext";
import {
  useSemanticGraph,
  type Domain,
  type EntityDetail,
} from "../hooks/useSemanticGraph";
import SemanticGraph from "../components/semantic/SemanticGraph";
import EntityPanel from "../components/semantic/EntityPanel";

const DOMAIN_OPTIONS: ("all" | Domain)[] = [
  "all",
  "wealth_mgmt",
  "accounting",
  "crm",
  "hr",
  "planning",
  "unspecified",
];

export default function Semantic() {
  const { state } = useAppState();
  const { theme } = useTheme();

  const connections = state.workspaceConnections.filter(
    (c) => c.status === "live"
  );
  const [selectedConnId, setSelectedConnId] = useState<string | null>(
    connections[0]?.connection_id ?? null
  );
  // Auto-select the first live connection when the list resolves.
  useEffect(() => {
    if (!selectedConnId && connections.length) {
      setSelectedConnId(connections[0].connection_id);
    }
  }, [connections, selectedConnId]);

  const { snapshot, isLoading, error, domain, setDomain, loadEntity } =
    useSemanticGraph(selectedConnId);

  const [selectedEntityId, setSelectedEntityId] = useState<string | null>(null);
  const [detail, setDetail] = useState<EntityDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    if (!selectedEntityId) {
      setDetail(null);
      return;
    }
    setDetailLoading(true);
    void loadEntity(selectedEntityId).then((d) => {
      if (cancelled) return;
      setDetail(d);
      setDetailLoading(false);
    });
    return () => {
      cancelled = true;
    };
  }, [selectedEntityId, loadEntity]);

  const kpis = snapshot?.kpi_strip ?? null;

  const tiles = useMemo(
    () => [
      { label: "Entities", value: kpis?.entities ?? 0 },
      { label: "Metrics", value: kpis?.metrics ?? 0 },
      { label: "Joins", value: kpis?.joins ?? 0 },
      { label: "Bindings", value: kpis?.bindings ?? 0 },
    ],
    [kpis]
  );

  if (connections.length === 0) {
    return (
      <div className="p-6">
        <h1
          className="text-2xl font-semibold"
          style={{ color: theme.colors.textPrimary }}
        >
          Semantic
        </h1>
        <div
          className="rounded-lg p-6 text-sm mt-4"
          style={{
            color: theme.colors.textSecondary,
            backgroundColor: theme.colors.surfaceSubtle,
            border: `1px dashed ${theme.colors.borderSubtle}`,
          }}
        >
          No live connections — add one on the Connections page.
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4 p-6">
      <header className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1
            className="text-2xl font-semibold"
            style={{ color: theme.colors.textPrimary }}
          >
            Semantic
          </h1>
          <p
            className="text-sm mt-1"
            style={{ color: theme.colors.textSecondary }}
          >
            Per-connection graph of entities, metrics, and joins. Each
            connection's graph is independent (Q2 — no cross-connection
            reconciliation in v1).
          </p>
        </div>
        <div className="flex items-center gap-2">
          <select
            data-testid="connection-switcher"
            value={selectedConnId ?? ""}
            onChange={(e) => {
              setSelectedConnId(e.target.value || null);
              setSelectedEntityId(null);
            }}
            className="text-sm px-2 py-1 rounded"
            style={{
              backgroundColor: theme.colors.white,
              color: theme.colors.textPrimary,
              border: `1px solid ${theme.colors.borderSubtle}`,
            }}
          >
            {connections.map((c) => (
              <option key={c.connection_id} value={c.connection_id}>
                {c.display_name} · {c.scope}
              </option>
            ))}
          </select>
          <select
            data-testid="domain-filter"
            value={domain}
            onChange={(e) => setDomain(e.target.value as "all" | Domain)}
            className="text-sm px-2 py-1 rounded"
            style={{
              backgroundColor: theme.colors.white,
              color: theme.colors.textPrimary,
              border: `1px solid ${theme.colors.borderSubtle}`,
            }}
          >
            {DOMAIN_OPTIONS.map((d) => (
              <option key={d} value={d}>
                {d.replace("_", " ")}
              </option>
            ))}
          </select>
        </div>
      </header>

      {error ? (
        <div
          role="alert"
          className="text-xs px-3 py-2 rounded"
          style={{ color: "#DC2626", backgroundColor: "#DC262614" }}
        >
          {error}
        </div>
      ) : null}

      {/* KPI strip */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
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
              className="text-lg font-semibold tabular-nums"
              style={{ color: theme.colors.textPrimary }}
            >
              {t.value.toLocaleString()}
            </div>
          </div>
        ))}
      </div>

      {/* Graph + side panel */}
      <div className="grid grid-cols-1 lg:grid-cols-[1fr_320px] gap-4">
        {snapshot ? (
          <SemanticGraph
            entities={snapshot.entities}
            joins={snapshot.joins}
            selectedEntityId={selectedEntityId}
            onSelect={setSelectedEntityId}
          />
        ) : (
          <div
            data-testid="semantic-empty"
            className="rounded-lg p-6 text-sm"
            style={{
              color: theme.colors.textSecondary,
              backgroundColor: theme.colors.surfaceSubtle,
              border: `1px dashed ${theme.colors.borderSubtle}`,
              minHeight: 420,
            }}
          >
            {isLoading
              ? "loading semantic graph…"
              : "no semantic data yet for this connection — provision a PRD to populate."}
          </div>
        )}
        {selectedEntityId ? (
          <EntityPanel
            detail={detail}
            loading={detailLoading}
            onClose={() => setSelectedEntityId(null)}
          />
        ) : (
          <div
            data-testid="entity-panel-placeholder"
            className="rounded-lg p-6 text-sm"
            style={{
              color: theme.colors.textTertiary,
              backgroundColor: theme.colors.surfaceSubtle,
              border: `1px dashed ${theme.colors.borderSubtle}`,
              minHeight: 280,
            }}
          >
            Select a node to inspect its attributes, metrics, and bindings.
          </div>
        )}
      </div>
    </div>
  );
}
