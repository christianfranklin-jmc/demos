// useProvisioningRun — SSE consumer for /workflow/provision/{run_id}/events (T086, US3).
//
// Subscribes to the v2 event stream and maintains an in-memory snapshot
// of the run's state: per-agent state machine, KPI series, validation
// results, terminal product. Reconnects on transport errors with a
// short backoff; cancels cleanly on unmount via AbortController.

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { getOrMintSessionId } from "../lib/session";
import {
  streamEvents,
  type AgentId,
  type AgentState,
  type ArtifactRef,
  type KpiTick,
  type ProvisionEventV2,
} from "../lib/agentcore-client/parsers/v2";

const BACKEND_URL: string =
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  (import.meta as any).env?.VITE_BACKEND_URL ?? "http://localhost:8080";

export const AGENT_ORDER: AgentId[] = [
  "schema",
  "pipeline",
  "model",
  "quality",
  "mapping",
  "semantic",
  "delivery",
];

export interface AgentSnapshot {
  agent_id: AgentId;
  state: AgentState;
  attempt: number;
  artifacts: ArtifactRef[];
  message: string | null;
  error_code: string | null;
  error_message: string | null;
  latency_ms_p95: number | null;
  started_at: string | null;
  completed_at: string | null;
}

export interface ValidationRow {
  question: string;
  state: "passed" | "failed";
  sql_executed: string | null;
  latency_ms: number | null;
  judge_reasoning: string;
}

export interface ActivityRow {
  ts: string;
  agent_id: AgentId | null;
  message: string;
  /** Coarse classification for icon/color in ActivityStream. */
  level: "info" | "success" | "warn" | "error";
}

export type RunState =
  | "idle"
  | "running"
  | "completed"
  | "needs_replan"
  | "failed"
  | "stream_error";

export interface ProvisioningRunState {
  run_id: string | null;
  state: RunState;
  agents: AgentSnapshot[];
  ticks: KpiTick[];
  artifacts: ArtifactRef[];
  validation_results: ValidationRow[];
  activity: ActivityRow[];
  product_id: string | null;
  product_state: "final" | "provisional" | null;
  validation_pass_rate: number | null;
  needs_replan_reason: string | null;
  error: string | null;
}

const INITIAL_AGENT = (id: AgentId): AgentSnapshot => ({
  agent_id: id,
  state: "pending",
  attempt: 1,
  artifacts: [],
  message: null,
  error_code: null,
  error_message: null,
  latency_ms_p95: null,
  started_at: null,
  completed_at: null,
});

export function emptyRunState(): ProvisioningRunState {
  return {
    run_id: null,
    state: "idle",
    agents: AGENT_ORDER.map(INITIAL_AGENT),
    ticks: [],
    artifacts: [],
    validation_results: [],
    activity: [],
    product_id: null,
    product_state: null,
    validation_pass_rate: null,
    needs_replan_reason: null,
    error: null,
  };
}

function reduce(
  prev: ProvisioningRunState,
  event: ProvisionEventV2
): ProvisioningRunState {
  switch (event.kind) {
    case "heartbeat":
      return prev;

    case "agent.started": {
      return {
        ...prev,
        state: "running",
        agents: prev.agents.map((a) =>
          a.agent_id === event.agent_id
            ? {
                ...a,
                state: "active",
                attempt: event.attempt,
                started_at: event.ts,
                error_code: null,
                error_message: null,
              }
            : a
        ),
        activity: pushActivity(prev.activity, {
          ts: event.ts,
          agent_id: event.agent_id,
          message: `started (attempt ${event.attempt})`,
          level: "info",
        }),
      };
    }

    case "agent.progress":
      return {
        ...prev,
        agents: prev.agents.map((a) =>
          a.agent_id === event.agent_id ? { ...a, message: event.message } : a
        ),
        activity: pushActivity(prev.activity, {
          ts: event.ts,
          agent_id: event.agent_id,
          message: event.message,
          level: "info",
        }),
      };

    case "agent.completed":
      return {
        ...prev,
        agents: prev.agents.map((a) =>
          a.agent_id === event.agent_id
            ? {
                ...a,
                state: "completed",
                completed_at: event.ts,
                artifacts: event.artifacts,
                latency_ms_p95: event.latency_ms_p95,
                message: null,
              }
            : a
        ),
        activity: pushActivity(prev.activity, {
          ts: event.ts,
          agent_id: event.agent_id,
          message: `completed · ${event.artifacts.length} artifact(s)`,
          level: "success",
        }),
      };

    case "agent.failed":
      return {
        ...prev,
        agents: prev.agents.map((a) =>
          a.agent_id === event.agent_id
            ? {
                ...a,
                state: "failed",
                completed_at: event.ts,
                error_code: event.error_code,
                error_message: event.error_message,
              }
            : a
        ),
        activity: pushActivity(prev.activity, {
          ts: event.ts,
          agent_id: event.agent_id,
          message: `failed: ${event.error_message}`,
          level: "error",
        }),
      };

    case "kpi.tick":
      return { ...prev, ticks: [...prev.ticks, event.tick] };

    case "artifact.produced":
      return {
        ...prev,
        artifacts: [...prev.artifacts, event.artifact],
        activity: pushActivity(prev.activity, {
          ts: event.ts,
          agent_id: event.agent_id,
          message: `${event.artifact.kind}: ${event.artifact.ref}`,
          level: "info",
        }),
      };

    case "validation.started":
      return {
        ...prev,
        activity: pushActivity(prev.activity, {
          ts: event.ts,
          agent_id: "delivery",
          message: `validating ${event.question_count} question(s)`,
          level: "info",
        }),
      };

    case "validation.result":
      return {
        ...prev,
        validation_results: [
          ...prev.validation_results,
          {
            question: event.question,
            state: event.state,
            sql_executed: event.sql_executed,
            latency_ms: event.latency_ms,
            judge_reasoning: event.judge_reasoning,
          },
        ],
        activity: pushActivity(prev.activity, {
          ts: event.ts,
          agent_id: "delivery",
          message: `${event.state}: ${truncate(event.question, 60)}`,
          level: event.state === "passed" ? "success" : "warn",
        }),
      };

    case "run.completed":
      return {
        ...prev,
        state: event.product_state === "final" ? "completed" : "needs_replan",
        product_id: event.product_id,
        product_state: event.product_state,
        validation_pass_rate: event.validation_pass_rate,
        activity: pushActivity(prev.activity, {
          ts: event.ts,
          agent_id: null,
          message: `run.completed → ${event.product_state} (${(
            event.validation_pass_rate * 100
          ).toFixed(0)}%)`,
          level: event.product_state === "final" ? "success" : "warn",
        }),
      };

    case "run.needs_replan":
      return {
        ...prev,
        state: "needs_replan",
        needs_replan_reason: event.reason,
        activity: pushActivity(prev.activity, {
          ts: event.ts,
          agent_id: event.suggested_agent,
          message: `needs replan: ${event.reason}`,
          level: "warn",
        }),
      };

    default: {
      // Exhaustiveness — TS will complain if we add a kind without a case.
      const _exhaustive: never = event;
      void _exhaustive;
      return prev;
    }
  }
}

function pushActivity(
  rows: ActivityRow[],
  next: ActivityRow,
  cap = 200
): ActivityRow[] {
  const merged = [...rows, next];
  return merged.length > cap ? merged.slice(merged.length - cap) : merged;
}

function truncate(s: string, max: number): string {
  return s.length <= max ? s : s.slice(0, max - 1) + "…";
}

export function useProvisioningRun(run_id: string | null) {
  const [snapshot, setSnapshot] = useState<ProvisioningRunState>(emptyRunState);
  const sessionId = useMemo(() => getOrMintSessionId(), []);
  const ctrl = useRef<AbortController | null>(null);

  // Reset whenever the run_id changes.
  useEffect(() => {
    setSnapshot({ ...emptyRunState(), run_id });
  }, [run_id]);

  useEffect(() => {
    if (!run_id) return;
    ctrl.current?.abort();
    const controller = new AbortController();
    ctrl.current = controller;

    void (async () => {
      try {
        for await (const ev of streamEvents(
          `${BACKEND_URL}/workflow/provision/${encodeURIComponent(run_id)}/events`,
          {
            method: "GET",
            signal: controller.signal,
            headers: { "X-DSA-Session-ID": sessionId },
          }
        )) {
          if (controller.signal.aborted) break;
          setSnapshot((prev) => reduce(prev, ev));
        }
      } catch (exc: unknown) {
        if (controller.signal.aborted) return;
        setSnapshot((prev) => ({
          ...prev,
          state: "stream_error",
          error: exc instanceof Error ? exc.message : String(exc),
        }));
      }
    })();
    return () => {
      controller.abort();
    };
  }, [run_id, sessionId]);

  const retry = useCallback(
    async (agent_id: AgentId): Promise<void> => {
      if (!run_id) return;
      await fetch(
        `${BACKEND_URL}/workflow/provision/${encodeURIComponent(run_id)}/retry`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-DSA-Session-ID": sessionId,
          },
          body: JSON.stringify({ agent_id }),
        }
      );
    },
    [run_id, sessionId]
  );

  return { snapshot, retry };
}
