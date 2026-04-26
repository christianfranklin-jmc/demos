// useSemanticGraph — per-connection semantic graph fetcher (T111, US5).

import { useCallback, useEffect, useMemo, useState } from "react";
import { getOrMintSessionId } from "../lib/session";

const BACKEND_URL: string =
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  (import.meta as any).env?.VITE_BACKEND_URL ?? "http://localhost:8080";

export type Domain =
  | "wealth_mgmt"
  | "accounting"
  | "crm"
  | "hr"
  | "planning"
  | "unspecified";

export type Cardinality = "one_to_one" | "one_to_many" | "many_to_many";

export interface GraphEntityRow {
  entity_id: string;
  name: string;
  domain: Domain;
  metric_count: number;
  binding_count: number;
  version: number;
}

export interface GraphJoinRow {
  join_id: string;
  left_entity_id: string;
  right_entity_id: string;
  cardinality: Cardinality;
}

export interface GraphKPIStrip {
  entities: number;
  metrics: number;
  joins: number;
  bindings: number;
  processes_mapped_pct: number;
}

export interface SemanticGraphSnapshot {
  connection_id: string;
  entities: GraphEntityRow[];
  joins: GraphJoinRow[];
  kpi_strip: GraphKPIStrip;
}

export interface EntityDetail {
  entity: {
    entity_id: string;
    name: string;
    domain: Domain;
    attributes: { name: string; data_type: string; is_pii: boolean }[];
    metric_ids: string[];
    physical_binding_ids: string[];
    version: number;
    created_at: string;
    updated_at: string;
  };
  bindings: {
    binding_id: string;
    fully_qualified_name: string;
    column_map: Record<string, string>;
    row_count_estimate: number | null;
  }[];
  metrics: {
    metric_id: string;
    name: string;
    definition_sql: string;
    unit: string | null;
  }[];
}

export function useSemanticGraph(connection_id: string | null) {
  const [snapshot, setSnapshot] = useState<SemanticGraphSnapshot | null>(null);
  const [domain, setDomain] = useState<Domain | "all">("all");
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const sessionId = useMemo(() => getOrMintSessionId(), []);
  const headers = useMemo(
    () => ({ "X-DSA-Session-ID": sessionId }),
    [sessionId]
  );

  const refresh = useCallback(async (): Promise<void> => {
    if (!connection_id) {
      setSnapshot(null);
      return;
    }
    setIsLoading(true);
    try {
      const url = new URL(`${BACKEND_URL}/semantic/graph`);
      url.searchParams.set("connection_id", connection_id);
      if (domain !== "all") url.searchParams.set("domain", domain);
      const r = await fetch(url.toString(), { headers });
      if (r.status === 404) {
        setSnapshot(null);
        setError(null);
        return;
      }
      if (!r.ok) throw new Error(`semantic graph fetch failed: ${r.status}`);
      setSnapshot((await r.json()) as SemanticGraphSnapshot);
      setError(null);
    } catch (exc: unknown) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setIsLoading(false);
    }
  }, [connection_id, domain, headers]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const loadEntity = useCallback(
    async (entity_id: string): Promise<EntityDetail | null> => {
      if (!connection_id) return null;
      const url = new URL(`${BACKEND_URL}/semantic/entities/${encodeURIComponent(entity_id)}`);
      url.searchParams.set("connection_id", connection_id);
      const r = await fetch(url.toString(), { headers });
      if (r.status === 404) return null;
      if (!r.ok) throw new Error(`entity detail fetch failed: ${r.status}`);
      return (await r.json()) as EntityDetail;
    },
    [connection_id, headers]
  );

  return { snapshot, isLoading, error, domain, setDomain, refresh, loadEntity };
}
