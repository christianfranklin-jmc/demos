// Step1Discovery — multi-source business-process discovery + pilled PRDs (T058, US2).
//
// Replaces the single-source Step 1 freeform PRD when the workspace
// has ≥2 live connections. Renders three stacked sections per the spec:
//
//   (a) Detected business processes — auto-discovered cards (FR-009).
//   (b) Cross-source coverage matrix — process × connection grid (FR-010).
//   (c) Pilled PRDs — schema-grounded clickable chips (FR-011, FR-012).
//
// Pill click triggers /workflow/pills/{id}/draft-prd and forwards the
// resulting PRDDraft to the parent via onPillAccepted, which (in the
// existing AppShell) dispatches the workflow handoff to Step 2.

import { useMemo, useState } from "react";
import { useTheme } from "../context/ThemeContext";
import { useAppState } from "../context/AppContext";
import { usePills, type PRDDraft, type PillSuggestion } from "../hooks/usePills";
import { useWorkspaceDiscover } from "../hooks/useWorkspaceDiscover";
import ProcessCard from "../components/discovery/ProcessCard";
import CoverageMatrix from "../components/discovery/CoverageMatrix";
import PillRow from "../components/discovery/PillRow";

interface Props {
  onPillAccepted?: (pill: PillSuggestion, prd: PRDDraft) => void;
}

export default function Step1Discovery({ onPillAccepted }: Props) {
  const { state } = useAppState();
  const { theme } = useTheme();
  const { discovery, isLoading: discoveryLoading, error: discoveryError, refresh } =
    useWorkspaceDiscover();
  const { pills, isLoading: pillsLoading, error: pillsError, draftPrd } = usePills();
  const [selecting, setSelecting] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const liveConnections = useMemo(
    () => state.workspaceConnections.filter((c) => c.status === "live"),
    [state.workspaceConnections]
  );

  // Aggregate KPI strip across the workspace + per-connection envelopes.
  const kpis = useMemo(() => {
    const tables = (discovery?.per_connection ?? []).reduce(
      (acc, env) => acc + env.kpi_summary.tables_scanned,
      0
    );
    const columns = (discovery?.per_connection ?? []).reduce(
      (acc, env) => acc + env.kpi_summary.columns_profiled,
      0
    );
    const processes = (discovery?.per_connection ?? []).reduce(
      (acc, env) => acc + env.kpi_summary.processes_detected,
      0
    );
    return {
      tables,
      columns,
      processes,
      crossLinks: discovery?.cross_source_links_found ?? 0,
      pills: pills.length,
    };
  }, [discovery, pills]);

  if (liveConnections.length === 0) {
    return (
      <div className="flex flex-col gap-4 p-6">
        <h1
          className="text-2xl font-semibold"
          style={{ color: theme.colors.textPrimary }}
        >
          Discovery
        </h1>
        <div
          className="rounded-lg p-6 text-sm"
          style={{
            color: theme.colors.textSecondary,
            backgroundColor: theme.colors.surfaceSubtle,
            border: `1px dashed ${theme.colors.borderSubtle}`,
          }}
          data-testid="discovery-empty"
        >
          Add at least one connection in the Connections page to run discovery.
        </div>
      </div>
    );
  }

  const onSelectPill = async (pill: PillSuggestion) => {
    setSelecting(pill.pill_id);
    setError(null);
    try {
      const prd = await draftPrd(pill.pill_id);
      if (prd && onPillAccepted) onPillAccepted(pill, prd);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setSelecting(null);
    }
  };

  return (
    <div className="flex flex-col gap-6 p-6">
      <header className="flex items-start justify-between gap-4">
        <div>
          <h1
            className="text-2xl font-semibold"
            style={{ color: theme.colors.textPrimary }}
          >
            Discovery
          </h1>
          <p
            className="text-sm mt-1"
            style={{ color: theme.colors.textSecondary }}
          >
            Business processes detected from your live connections, the cross-
            source coverage map, and schema-grounded pilled PRDs that combine
            sources into governed Iceberg data products.
          </p>
        </div>
        <button
          type="button"
          onClick={() => refresh(true)}
          className="px-3 py-2 rounded text-sm shrink-0"
          style={{
            color: theme.colors.textSecondary,
            border: `1px solid ${theme.colors.borderSubtle}`,
          }}
          disabled={discoveryLoading}
        >
          {discoveryLoading ? "Re-discovering…" : "Re-discover"}
        </button>
      </header>

      {/* KPI strip */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        <KpiTile label="Tables scanned" value={kpis.tables} />
        <KpiTile label="Columns profiled" value={kpis.columns} />
        <KpiTile label="Processes detected" value={kpis.processes} />
        <KpiTile label="Cross-source links" value={kpis.crossLinks} />
        <KpiTile label="Pills generated" value={kpis.pills} />
      </div>

      {(discoveryError || pillsError || error) && (
        <div
          role="alert"
          className="text-xs px-3 py-2 rounded"
          style={{
            color: "#DC2626",
            backgroundColor: "#DC262614",
          }}
        >
          {discoveryError ?? pillsError ?? error}
        </div>
      )}

      {/* (a) Detected business processes */}
      <section className="flex flex-col gap-3">
        <SectionTitle
          label="Detected business processes"
          count={discovery?.per_connection.reduce((a, e) => a + e.processes.length, 0) ?? 0}
        />
        {discoveryLoading && !discovery ? (
          <SkeletonGrid />
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {(discovery?.per_connection ?? []).flatMap((env) =>
              env.processes.map((p) => (
                <ProcessCard
                  key={p.process_id}
                  process={p}
                  connections={liveConnections}
                />
              ))
            )}
          </div>
        )}
      </section>

      {/* (b) Cross-source coverage map */}
      <section className="flex flex-col gap-3">
        <SectionTitle
          label="Cross-source coverage"
          count={discovery?.coverage_matrix.rows.length ?? 0}
        />
        {discovery ? (
          <CoverageMatrix
            matrix={discovery.coverage_matrix}
            connections={liveConnections}
          />
        ) : null}
      </section>

      {/* (c) Pilled PRDs */}
      <section className="flex flex-col gap-3">
        <SectionTitle
          label="Pilled PRDs"
          count={pills.length}
          hint="Click a pill to draft a complete cross-source PRD."
        />
        {pillsLoading && !pills.length ? <SkeletonGrid /> : null}
        <PillRow pills={pills} onSelect={onSelectPill} isSelecting={selecting} />
      </section>
    </div>
  );
}

function KpiTile({ label, value }: { label: string; value: number }) {
  const { theme } = useTheme();
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
        {value.toLocaleString()}
      </span>
    </div>
  );
}

function SectionTitle({
  label,
  count,
  hint,
}: {
  label: string;
  count: number;
  hint?: string;
}) {
  const { theme } = useTheme();
  return (
    <div className="flex items-baseline justify-between">
      <h2
        className="text-base font-semibold"
        style={{ color: theme.colors.textPrimary }}
      >
        {label}{" "}
        <span
          className="text-sm tabular-nums"
          style={{ color: theme.colors.textTertiary }}
        >
          ({count})
        </span>
      </h2>
      {hint ? (
        <span
          className="text-xs"
          style={{ color: theme.colors.textTertiary }}
        >
          {hint}
        </span>
      ) : null}
    </div>
  );
}

function SkeletonGrid() {
  const { theme } = useTheme();
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
      {[0, 1, 2].map((i) => (
        <div
          key={i}
          className="rounded-lg p-4 h-24 animate-pulse"
          style={{
            backgroundColor: theme.colors.surfaceSubtle,
            border: `1px solid ${theme.colors.borderSubtle}`,
          }}
        />
      ))}
    </div>
  );
}
