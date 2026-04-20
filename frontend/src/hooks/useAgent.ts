/**
 * useAgent — step dispatcher to the PlatformAgent backend.
 *
 * Public API preserved from the DSA pre-scripted engine: `useAgent()` is a
 * side-effect hook installed once in ChatPanel.tsx. It watches conversation
 * state for new user messages and dispatches a backend call per step.
 *
 * Split between two modes (FR-015 / ADR-015 D13):
 *   - Live mode:  POST /workflow/step, stream SSE events, drive AppContext.
 *   - Demo mode:  delegate to the pre-scripted engine in useAgent.demo.ts.
 *
 * Step-specific artifact rendering (PRD, ERD, logical model, zip download)
 * lands in T041–T044 (Phase 3 US1). This file ships the shell only: it
 * correctly POSTs, consumes the SSE stream, handles terminal events and the
 * 30-second silence timer, and surfaces errors. TODOs mark where the
 * Phase-3 tasks plug in per-step payload handling.
 */

import { useEffect, useRef } from "react";
import { useAppState } from "../context/AppContext";
import { useAgentDemo } from "./useAgent.demo";
import { STEP_NUMBER_TO_ID } from "../lib/types";
import type {
  SSEEventV1,
  StepId,
  StepRequest,
  ConversationMessage,
  PrdPayload,
  ConceptualModelPayload,
  LogicalModelPayload,
} from "../lib/types";
import {
  SilenceTimer,
  streamEvents,
} from "../lib/agentcore-client/parsers/v1";
import {
  conceptualFromBackend,
  logicalFromBackend,
  prdFromBackend,
} from "../lib/adapters";

const BACKEND_URL =
  (import.meta as any).env?.VITE_BACKEND_URL ?? "http://localhost:8080";

export interface RunStepController {
  abort: () => void;
  runId: string | null;
}

// Module-level handle to the currently-streaming run for the Cancel button.
// The latest call replaces the previous value; only one run is in flight at
// a time from a single tab (useAgent enforces this).
let currentController: RunStepController | null = null;

export function getCurrentRun(): RunStepController | null {
  return currentController;
}

export function useAgent(): void {
  const { state, dispatch } = useAppState();

  // When demo mode is enabled, delegate entirely to the pre-scripted engine.
  // Live mode handlers must be conditional on !demoMode.enabled.
  useAgentDemo();

  const inFlightRef = useRef<RunStepController | null>(null);
  const lastSentIndexRef = useRef<number>(-1);

  useEffect(() => {
    if (state.demoMode.enabled) return; // demo engine owns message dispatch

    // Find the latest user message across the conversation that we have not
    // already submitted. Demo mode delegates; live mode submits here.
    const idx = lastUserIndex(state.conversation);
    if (idx < 0 || idx <= lastSentIndexRef.current) return;
    const message = state.conversation[idx];
    if (!message || message.message_role !== "user") return;

    lastSentIndexRef.current = idx;

    const stepId = STEP_NUMBER_TO_ID[message.step];
    if (!stepId) return; // step 0 (stakeholders) is out of scope for the backend

    // Fire-and-track the backend call. We do not await — this is an effect.
    inFlightRef.current = runStep(stepId, message.message_text, {
      sessionId: state.sessionId,
      connection: state.connection,
      dispatch,
    });
    currentController = inFlightRef.current;

    return () => {
      inFlightRef.current?.abort();
      if (currentController === inFlightRef.current) currentController = null;
      inFlightRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state.conversation, state.demoMode.enabled, state.sessionId]);
}

function lastUserIndex(conv: ConversationMessage[]): number {
  for (let i = conv.length - 1; i >= 0; i--) {
    if (conv[i].message_role === "user") return i;
  }
  return -1;
}

interface RunStepContext {
  sessionId: string;
  connection: StepRequest["connection"];
  dispatch: ReturnType<typeof useAppState>["dispatch"];
}

/**
 * Invoke `POST /workflow/step` and stream the SSE response. Side effects are
 * applied via `ctx.dispatch`. Returns an {abort} handle so the caller can
 * cancel on unmount.
 */
export function runStep(
  stepId: StepId,
  userMessage: string,
  ctx: RunStepContext,
): RunStepController {
  const abortCtl = new AbortController();
  const controller: RunStepController = {
    abort: () => abortCtl.abort(),
    runId: null,
  };
  const body: StepRequest = {
    step_id: stepId,
    user_message: userMessage,
    prior_artifact: null, // Future: thread prior-step artifacts through here.
    connection: ctx.connection,
    resume: false,
  };

  void (async () => {
    ctx.dispatch({ type: "SET_AGENT_THINKING", thinking: true });
    let silence: SilenceTimer | null = null;
    try {
      const response = await fetch(`${BACKEND_URL}/workflow/step`, {
        method: "POST",
        signal: abortCtl.signal,
        headers: {
          "Content-Type": "application/json",
          Accept: "text/event-stream",
          "X-DSA-Session-ID": ctx.sessionId,
        },
        body: JSON.stringify(body),
      });

      if (!response.ok) {
        const text = await response.text().catch(() => "");
        throw new Error(`HTTP ${response.status}: ${text || response.statusText}`);
      }

      controller.runId = response.headers.get("X-Run-Id");

      silence = new SilenceTimer(() => {
        abortCtl.abort(new DOMException("Silence timeout", "TimeoutError"));
      });

      for await (const event of streamEvents(response, silence)) {
        handleEvent(event, ctx);
      }
    } catch (err) {
      if (abortCtl.signal.aborted) return;
      const message = err instanceof Error ? err.message : String(err);
      console.error("runStep error:", message);
      // TODO(T064): offer "Continue in demo mode" affordance on error.
    } finally {
      silence?.dispose();
      ctx.dispatch({ type: "SET_AGENT_THINKING", thinking: false });
    }
  })();

  return controller;
}

/**
 * Dispatch an SSE event to AppContext. Per-step artifact rendering is a TODO
 * that Phase 3 tasks T041-T044 fill in.
 */
function handleEvent(event: SSEEventV1, ctx: RunStepContext): void {
  switch (event.event) {
    case "heartbeat":
      return; // no UI effect; silence timer bump already handled in the stream

    case "tool_start":
    case "tool_progress":
    case "tool_result":
      // Progress pane rendering is additive UX; the current chat shell is
      // sufficient for MVP. A dedicated progress component can consume these
      // events without changing this dispatcher.
      return;

    case "message":
      // Assistant streaming output. For MVP we concatenate into the last agent
      // chat bubble for the current step.
      ctx.dispatch({
        type: "ADD_MESSAGE",
        message: {
          data_product_id: "live",
          step: 1, // step-number specificity happens in a later pass; renderers
                   // filter by current_step which the reducer already tracks.
          message_role: "agent",
          message_text: event.content,
          timestamp: new Date().toISOString(),
        } as any,
      });
      return;

    case "artifact_update":
      if (event.artifact_type === "prd") {
        ctx.dispatch({
          type: "UPDATE_PRD",
          updates: prdFromBackend(event.payload as PrdPayload),
        });
      } else if (event.artifact_type === "conceptual_model") {
        ctx.dispatch({
          type: "SET_CONCEPTUAL_MODEL",
          model: conceptualFromBackend(event.payload as ConceptualModelPayload),
        });
      } else if (event.artifact_type === "logical_model") {
        ctx.dispatch({
          type: "SET_LOGICAL_MODEL",
          model: logicalFromBackend(event.payload as LogicalModelPayload),
        });
      }
      return;

    case "artifact_ready":
      void triggerZipDownload(event.download_url, ctx.sessionId);
      return;

    case "done":
      // Step completed; terminal. The silence timer is disposed by the loop.
      return;

    case "error":
      if (event.code === "memory_unreachable") {
        ctx.dispatch({ type: "MEMORY_STATUS_SET", status: "unreachable" });
      }
      // TODO(T064): render a toast/inline error; offer retry if retriable.
      return;

    default: {
      // Exhaustiveness guard — if SSEEventV1 grows a new variant, TS catches it here.
      const _exhaustive: never = event;
      void _exhaustive;
    }
  }
}

/**
 * T044: fetch the zip at `/workflow/artifact/{handle}` and trigger a browser
 * download via a hidden <a download> link.
 */
async function triggerZipDownload(downloadUrl: string, sessionId: string): Promise<void> {
  try {
    const response = await fetch(`${BACKEND_URL}${downloadUrl}`, {
      method: "GET",
      headers: { "X-DSA-Session-ID": sessionId },
    });
    if (!response.ok) {
      console.error("Zip download failed:", response.status, await response.text().catch(() => ""));
      return;
    }
    const blob = await response.blob();
    const objectUrl = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = objectUrl;
    anchor.download = filenameFromDisposition(
      response.headers.get("Content-Disposition") ?? "",
    ) ?? `dbt-project-${Date.now()}.zip`;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(objectUrl);
  } catch (err) {
    console.error("Zip download error:", err);
  }
}

function filenameFromDisposition(disposition: string): string | null {
  const match = /filename="([^"]+)"/.exec(disposition);
  return match ? match[1] : null;
}
