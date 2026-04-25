// Fire POST /workflow/discover whenever a connection is (re)established and
// dispatch SOURCE_CONTEXT_SET with the result. Cleared automatically by
// CONNECTION_CLEAR in the reducer.
//
// Runs once per connection identity — serialising driver_type/database/host
// into a cache key so switching databases re-runs discovery, but an
// unrelated re-render does not.

import { useEffect, useRef } from "react";
import { useAppState } from "../context/AppContext";
import { getOrMintSessionId } from "../lib/session";
import { getIdToken, isAuthEnabled } from "../lib/auth";
import type { SourceContext } from "../lib/types";

const BACKEND_URL =
  (import.meta as any).env?.VITE_BACKEND_URL ?? "http://localhost:8080";

interface DiscoverResponseRaw {
  product_name: string;
  domain_summary: string;
  business_processes: SourceContext["businessProcesses"];
  suggested_questions: string[];
  step_suggestions: Record<"1" | "2" | "3" | "4", string[]>;
}

function connectionKey(c: any): string {
  if (!c) return "";
  return [c.driver_type, c.database, c.host ?? c.account ?? "", c.schema ?? ""].join("|");
}

export function useSourceDiscovery(): void {
  const { state, dispatch } = useAppState();
  const lastKey = useRef<string>("");

  useEffect(() => {
    const key = connectionKey(state.connection);
    if (!state.connection || !key) {
      lastKey.current = "";
      return;
    }
    if (lastKey.current === key) return; // already discovered this source
    lastKey.current = key;

    const ctl = new AbortController();
    void (async () => {
      try {
        const headers: Record<string, string> = {
          "Content-Type": "application/json",
          "X-DSA-Session-ID": getOrMintSessionId(),
        };
        if (isAuthEnabled()) {
          const t = getIdToken();
          if (t) headers.Authorization = `Bearer ${t}`;
        }
        const r = await fetch(`${BACKEND_URL}/workflow/discover`, {
          method: "POST",
          headers,
          signal: ctl.signal,
          body: JSON.stringify({ connection: state.connection }),
        });
        if (!r.ok) {
          console.warn("discover: HTTP", r.status, await r.text().catch(() => ""));
          return;
        }
        const raw = (await r.json()) as DiscoverResponseRaw;
        const context: SourceContext = {
          productName: raw.product_name,
          domainSummary: raw.domain_summary,
          businessProcesses: raw.business_processes ?? [],
          suggestedQuestions: raw.suggested_questions ?? [],
          stepSuggestions: raw.step_suggestions ?? { "1": [], "2": [], "3": [], "4": [] },
        };
        dispatch({ type: "SOURCE_CONTEXT_SET", context });
      } catch (err) {
        if ((err as any)?.name !== "AbortError") {
          console.warn("discover failed:", err);
        }
      }
    })();

    return () => ctl.abort();
  }, [state.connection, dispatch]);
}
