// usePills — pill suggestions hook (T062, US2).
//
// Calls POST /workflow/pills to fetch the schema-grounded suggestion set
// for the current workspace, and POST /workflow/pills/{id}/draft-prd when
// a pill is clicked.

import { useCallback, useEffect, useMemo, useState } from "react";
import { getOrMintSessionId } from "../lib/session";

const BACKEND_URL: string =
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  (import.meta as any).env?.VITE_BACKEND_URL ?? "http://localhost:8080";

export interface PillFlags {
  demo: boolean;
}

export interface PillSuggestion {
  pill_id: string;
  title: string;
  subtitle: string;
  icon: string;
  target_iceberg_table: string;
  source_connection_ids: string[];
  estimated_build_minutes: number;
  generated_at: string;
  flags: PillFlags;
  // seed_prd_body shape isn't surfaced here; consumers fetch the full
  // draft via draftPrd() on click.
}

export interface PRDDraft {
  prd_id: string;
  title: string;
  target: { connection_id: string; glue_db: string; table_name: string };
  business_questions: string[];
  source_pulls: { connection_id: string; sql: string; max_rows: number }[];
  standards_applied: string[];
  origin: "pill" | "manual";
  // (entities_proposed / metrics_proposed / joins_identified omitted for
  //  this hook — Step 2 reads them when it lands.)
}

export interface UsePillsReturn {
  pills: PillSuggestion[];
  isLoading: boolean;
  error: string | null;
  refresh: (force?: boolean) => Promise<void>;
  draftPrd: (pill_id: string) => Promise<PRDDraft | null>;
}

interface PillsResponse {
  pills: PillSuggestion[];
  generation_ms: number;
}

interface ErrorDetail {
  detail?: { code?: string; message?: string } | string;
}

export function usePills(opts?: { autoFetch?: boolean }): UsePillsReturn {
  const autoFetch = opts?.autoFetch ?? true;
  const [pills, setPills] = useState<PillSuggestion[]>([]);
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

  const refresh = useCallback(
    async (force: boolean = false): Promise<void> => {
      setIsLoading(true);
      try {
        const r = await fetch(`${BACKEND_URL}/workflow/pills`, {
          method: "POST",
          headers,
          body: JSON.stringify({ force, min_pills: 6 }),
        });
        if (r.status === 400) {
          // No live connections yet — clear silently.
          setPills([]);
          setError(null);
          return;
        }
        if (!r.ok) {
          let body: ErrorDetail | null = null;
          try {
            body = (await r.json()) as ErrorDetail;
          } catch {
            // ignore parse errors
          }
          const msg =
            typeof body?.detail === "string"
              ? body.detail
              : body?.detail?.message ?? `pill fetch failed (HTTP ${r.status})`;
          throw new Error(msg);
        }
        const data = (await r.json()) as PillsResponse;
        setPills(data.pills);
        setError(null);
      } catch (exc: unknown) {
        setError(exc instanceof Error ? exc.message : String(exc));
      } finally {
        setIsLoading(false);
      }
    },
    [headers]
  );

  const draftPrd = useCallback(
    async (pill_id: string): Promise<PRDDraft | null> => {
      const r = await fetch(
        `${BACKEND_URL}/workflow/pills/${encodeURIComponent(pill_id)}/draft-prd`,
        { method: "POST", headers }
      );
      if (r.status === 404) return null;
      if (!r.ok) throw new Error(`draft-prd failed (HTTP ${r.status})`);
      return (await r.json()) as PRDDraft;
    },
    [headers]
  );

  useEffect(() => {
    if (autoFetch) void refresh(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoFetch]);

  return { pills, isLoading, error, refresh, draftPrd };
}
