// useRedundancyCheck — pre-acceptance gate hook (T123, US6).

import { useCallback, useMemo } from "react";
import { getOrMintSessionId } from "../lib/session";

const BACKEND_URL: string =
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  (import.meta as any).env?.VITE_BACKEND_URL ?? "http://localhost:8080";

export type RedundancyState = "net_new" | "partial_overlap" | "duplicate";
export type OverlapKind = "entity" | "metric";

export interface OverlapItem {
  proposed_name: string;
  existing_id: string;
  kind: OverlapKind;
  overlap_pct: number;
  side_by_side_diff: string;
}

export interface RedundancyReport {
  report_id: string;
  prd_id: string;
  target_connection_id: string;
  state: RedundancyState;
  overlaps: OverlapItem[];
  decisions: { overlap_existing_id: string; kind: "reuse" | "override"; rationale: string }[];
  override_rationale: string | null;
  generated_at: string;
  cleared_to_provision: boolean;
}

export interface DecideResponse {
  cleared_to_provision: boolean;
  state: RedundancyState;
  pending_overlaps: number;
}

export function useRedundancyCheck() {
  const sessionId = useMemo(() => getOrMintSessionId(), []);
  const headers = useMemo(
    () => ({
      "Content-Type": "application/json",
      "X-DSA-Session-ID": sessionId,
    }),
    [sessionId]
  );

  const check = useCallback(
    async (prd: unknown): Promise<RedundancyReport> => {
      const r = await fetch(`${BACKEND_URL}/workflow/redundancy-check`, {
        method: "POST",
        headers,
        body: JSON.stringify({ prd }),
      });
      if (!r.ok) {
        let msg = `redundancy check failed (HTTP ${r.status})`;
        try {
          const body = await r.json();
          if (body?.detail?.message) msg = body.detail.message;
        } catch {
          // ignore
        }
        throw new Error(msg);
      }
      return (await r.json()) as RedundancyReport;
    },
    [headers]
  );

  const decide = useCallback(
    async (
      report_id: string,
      decisions: {
        overlap_existing_id: string;
        kind: "reuse" | "override";
        rationale: string;
      }[],
      override_rationale: string | null
    ): Promise<DecideResponse> => {
      const r = await fetch(
        `${BACKEND_URL}/workflow/redundancy-check/${encodeURIComponent(report_id)}/decide`,
        {
          method: "POST",
          headers,
          body: JSON.stringify({ decisions, override_rationale }),
        }
      );
      if (!r.ok) throw new Error(`decide failed (HTTP ${r.status})`);
      return (await r.json()) as DecideResponse;
    },
    [headers]
  );

  return { check, decide };
}
