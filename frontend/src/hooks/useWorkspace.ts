// useWorkspace — multi-source workspace state + connection CRUD (T043, US1).
//
// Talks to the backend's /workspace/* endpoints (contracts/workspace.openapi.yaml),
// keyed by the per-tab session UUID via the X-DSA-Session-ID header. Polls the
// connection list during the connecting → scanning → live lifecycle so the UI
// reflects status transitions within ~1 s.

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { getOrMintSessionId } from "../lib/session";

const BACKEND_URL: string =
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  (import.meta as any).env?.VITE_BACKEND_URL ?? "http://localhost:8080";

export type DriverType =
  | "postgresql"
  | "redshift"
  | "snowflake"
  | "databricks"
  | "iceberg";

export type ConnectionStatus = "connecting" | "scanning" | "live" | "error";

export interface ConnectionKPIs {
  tables_total: number;
  rows_estimated: number;
  processes_detected: number;
}

export interface ConnectionError {
  code: string;
  message: string;
  retryable: boolean;
}

export interface Connection {
  connection_id: string;
  driver_type: DriverType;
  display_name: string;
  endpoint: string;
  scope: string;
  credential_ref: string | null;
  status: ConnectionStatus;
  error: ConnectionError | null;
  kpis: ConnectionKPIs;
  added_at: string;
  last_synced_at: string | null;
  tags: string[];
}

export interface WorkspaceKPIs {
  sources_connected: number;
  tables_total: number;
  rows_total: number;
  processes_detected: number;
  semantic_entities_total: number;
  last_updated: string;
}

export interface AddConnectionInput {
  driver_type: DriverType;
  display_name: string;
  endpoint: string;
  scope: string;
  credentials: Record<string, unknown>;
  tags?: string[];
}

export interface AddConnectionError {
  /** Discriminator vs Connection (which has a string-union `status`). */
  kind: "error";
  http_status: number;
  code?: string;
  message: string;
}

export interface UseWorkspaceReturn {
  connections: Connection[];
  kpis: WorkspaceKPIs | null;
  isLoading: boolean;
  error: string | null;
  /** Refetch connections + KPIs once. */
  refresh: () => Promise<void>;
  add: (input: AddConnectionInput) => Promise<Connection | AddConnectionError>;
  remove: (connection_id: string) => Promise<void>;
  retry: (connection_id: string) => Promise<void>;
}

const POLL_MS_TRANSITIONING = 800;
const POLL_MS_STEADY = 4000;

/** Returns true while ≥1 connection is mid-lifecycle. */
function anyTransitioning(connections: Connection[]): boolean {
  return connections.some((c) => c.status === "connecting" || c.status === "scanning");
}

export function useWorkspace(): UseWorkspaceReturn {
  const [connections, setConnections] = useState<Connection[]>([]);
  const [kpis, setKpis] = useState<WorkspaceKPIs | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Same UUID for both the session and the workspace (Q1 + FR-006).
  const sessionId = useMemo(() => getOrMintSessionId(), []);
  const headers = useMemo(
    () => ({
      "Content-Type": "application/json",
      "X-DSA-Session-ID": sessionId,
    }),
    [sessionId]
  );

  const inflight = useRef<AbortController | null>(null);

  const refresh = useCallback(async (): Promise<void> => {
    inflight.current?.abort();
    const ctrl = new AbortController();
    inflight.current = ctrl;
    try {
      const [listRes, kpiRes] = await Promise.all([
        fetch(`${BACKEND_URL}/workspace/connections`, { headers, signal: ctrl.signal }),
        fetch(`${BACKEND_URL}/workspace/kpis`, { headers, signal: ctrl.signal }),
      ]);
      if (!listRes.ok || !kpiRes.ok) {
        throw new Error(
          `workspace fetch failed: connections=${listRes.status}, kpis=${kpiRes.status}`
        );
      }
      const listBody = (await listRes.json()) as { connections: Connection[] };
      const kpiBody = (await kpiRes.json()) as WorkspaceKPIs;
      setConnections(listBody.connections);
      setKpis(kpiBody);
      setError(null);
    } catch (exc: unknown) {
      if ((exc as { name?: string })?.name === "AbortError") return;
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setIsLoading(false);
    }
  }, [headers]);

  // Initial fetch + adaptive polling.
  useEffect(() => {
    void refresh();
    const interval = setInterval(
      () => {
        void refresh();
      },
      anyTransitioning(connections) ? POLL_MS_TRANSITIONING : POLL_MS_STEADY
    );
    return () => clearInterval(interval);
  }, [refresh, connections]);

  const add = useCallback(
    async (input: AddConnectionInput): Promise<Connection | AddConnectionError> => {
      const r = await fetch(`${BACKEND_URL}/workspace/connection`, {
        method: "POST",
        headers,
        body: JSON.stringify(input),
      });
      if (r.status === 201) {
        const created = (await r.json()) as Connection;
        await refresh();
        return created;
      }
      // 409 / 400 / 422 → return a structured error so the modal can render it.
      let body: unknown = null;
      try {
        body = await r.json();
      } catch {
        // empty
      }
      const detail = (body as { detail?: { code?: string; message?: string } | string })?.detail;
      const code = typeof detail === "object" ? detail?.code : undefined;
      const message =
        typeof detail === "string"
          ? detail
          : detail?.message ?? `Failed to add connection (HTTP ${r.status})`;
      return { kind: "error", http_status: r.status, code, message };
    },
    [headers, refresh]
  );

  const remove = useCallback(
    async (connection_id: string): Promise<void> => {
      const r = await fetch(`${BACKEND_URL}/workspace/connection/${connection_id}`, {
        method: "DELETE",
        headers,
      });
      if (r.status !== 204 && r.status !== 404) {
        throw new Error(`Failed to remove connection (HTTP ${r.status})`);
      }
      await refresh();
    },
    [headers, refresh]
  );

  const retry = useCallback(
    async (connection_id: string): Promise<void> => {
      const r = await fetch(`${BACKEND_URL}/workspace/connection/${connection_id}/retry`, {
        method: "POST",
        headers,
      });
      if (!r.ok) {
        throw new Error(`Failed to retry connection (HTTP ${r.status})`);
      }
      await refresh();
    },
    [headers, refresh]
  );

  return { connections, kpis, isLoading, error, refresh, add, remove, retry };
}
