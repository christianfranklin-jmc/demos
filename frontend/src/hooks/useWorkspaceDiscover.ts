// useWorkspaceDiscover — workspace-scoped discovery hook (T062, US2).
//
// Calls POST /workspace/discover when the workspace has ≥1 live connection;
// returns per-connection BusinessProcess lists + the workspace CoverageMatrix.
// Caches across re-renders; refreshes when the live-connection set changes.

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useAppState } from "../context/AppContext";
import { getOrMintSessionId } from "../lib/session";

const BACKEND_URL: string =
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  (import.meta as any).env?.VITE_BACKEND_URL ?? "http://localhost:8080";

export interface VolumeSignal {
  row_count: number;
  dollar_total: string | null;
  currency: string | null;
}

export interface BusinessProcess {
  process_id: string;
  connection_id: string;
  name: string;
  domain: "wealth_mgmt" | "accounting" | "crm" | "hr" | "planning" | "unspecified";
  volume_signal: VolumeSignal;
  last_activity_ts: string | null;
  sparkline: number[];
  backing_tables: string[];
}

export interface ProcessPresence {
  present: boolean;
  backing_tables: string[];
}

export interface CoverageRow {
  process_name: string;
  per_connection: Record<string, ProcessPresence>;
  shared_keys: string[];
  ready_to_combine: boolean;
}

export interface CoverageMatrix {
  matrix_id: string;
  rows: CoverageRow[];
}

export interface PerConnectionDiscovery {
  connection_id: string;
  processes: BusinessProcess[];
  kpi_summary: {
    tables_scanned: number;
    columns_profiled: number;
    processes_detected: number;
    elapsed_ms: number;
  };
}

export interface WorkspaceDiscoverResult {
  coverage_matrix: CoverageMatrix;
  per_connection: PerConnectionDiscovery[];
  cross_source_links_found: number;
}

export interface UseWorkspaceDiscoverReturn {
  discovery: WorkspaceDiscoverResult | null;
  isLoading: boolean;
  error: string | null;
  refresh: (force?: boolean) => Promise<void>;
}

export function useWorkspaceDiscover(): UseWorkspaceDiscoverReturn {
  const { state } = useAppState();
  const [discovery, setDiscovery] = useState<WorkspaceDiscoverResult | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const sessionId = useMemo(() => getOrMintSessionId(), []);
  const headers = useMemo(
    () => ({
      "Content-Type": "application/json",
      "X-DSA-Session-ID": sessionId,
    }),
    [sessionId]
  );

  // Fingerprint of the live connection set — refresh when it changes.
  const liveFingerprint = useMemo(
    () =>
      state.workspaceConnections
        .filter((c) => c.status === "live")
        .map((c) => c.connection_id)
        .sort()
        .join("|"),
    [state.workspaceConnections]
  );

  const inflight = useRef<AbortController | null>(null);

  const refresh = useCallback(
    async (force: boolean = false): Promise<void> => {
      inflight.current?.abort();
      const ctrl = new AbortController();
      inflight.current = ctrl;
      setIsLoading(true);
      try {
        const r = await fetch(`${BACKEND_URL}/workspace/discover`, {
          method: "POST",
          headers,
          body: JSON.stringify({ force }),
          signal: ctrl.signal,
        });
        if (r.status === 400) {
          setDiscovery(null);
          setError(null);
          return;
        }
        if (!r.ok) {
          throw new Error(`discover failed: ${r.status}`);
        }
        const body = (await r.json()) as WorkspaceDiscoverResult;
        setDiscovery(body);
        setError(null);
      } catch (exc: unknown) {
        if ((exc as { name?: string })?.name === "AbortError") return;
        setError(exc instanceof Error ? exc.message : String(exc));
      } finally {
        setIsLoading(false);
      }
    },
    [headers]
  );

  // Auto-refresh when the live connection set changes (debounced via fingerprint).
  useEffect(() => {
    if (liveFingerprint === "") {
      setDiscovery(null);
      return;
    }
    void refresh(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [liveFingerprint]);

  return { discovery, isLoading, error, refresh };
}
