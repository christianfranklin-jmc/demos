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
import { STEP_OPENERS } from "../data/step-openers";
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
import { getIdToken, isAuthEnabled } from "../lib/auth";

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

  // Live-mode opener: when the user enters a step with no messages, inject
  // a greeting + suggested replies so they have a starting point without
  // having to type their own prompt cold. Matches DSA's demo-engine pattern.
  useEffect(() => {
    if (state.demoMode.enabled) return; // demo engine owns openers in that mode
    const step = state.lifecycle.current_step;
    const opener = STEP_OPENERS[step];
    if (!opener) return;
    const stepMessages = state.conversation.filter((m) => m.step === step);
    if (stepMessages.length > 0) return;
    dispatch({
      type: "ADD_MESSAGE",
      message: {
        data_product_id: state.lifecycle.data_product_id,
        step,
        message_role: "agent",
        message_text: opener.greeting,
        suggested_replies: opener.suggestions,
        timestamp: new Date().toISOString(),
      } as any,
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state.lifecycle.current_step, state.demoMode.enabled]);

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
      currentStep: message.step,
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
  currentStep: number;
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
      const headers: Record<string, string> = {
        "Content-Type": "application/json",
        Accept: "text/event-stream",
        "X-DSA-Session-ID": ctx.sessionId,
      };
      if (isAuthEnabled()) {
        const idToken = getIdToken();
        if (idToken) headers.Authorization = `Bearer ${idToken}`;
      }
      const response = await fetch(`${BACKEND_URL}/workflow/step`, {
        method: "POST",
        signal: abortCtl.signal,
        headers,
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
      // T064: auto-fallback to demo mode so the demo keeps moving even when
      // the backend is unreachable. The DEMO_MODE_AUTO_ENABLE reducer action
      // stamps the reason so the UI can distinguish it from a user toggle.
      ctx.dispatch({ type: "DEMO_MODE_AUTO_ENABLE" });
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

    case "message": {
      // Attach the step's follow-up suggestions so the chat stays interactive
      // after the agent's closing message — otherwise the user has a reply
      // with no next action visible.
      const opener = STEP_OPENERS[ctx.currentStep as 0 | 1 | 2 | 3 | 4];
      ctx.dispatch({
        type: "ADD_MESSAGE",
        message: {
          data_product_id: "live",
          step: ctx.currentStep,
          message_role: "agent",
          message_text: event.content,
          suggested_replies: opener?.followups ?? [],
          timestamp: new Date().toISOString(),
        } as any,
      });
      return;
    }

    case "artifact_update":
      if (event.artifact_type === "prd") {
        // Live-mode PRD updates accumulate across turns — each clicked
        // suggestion refines the spec instead of clobbering it.
        ctx.dispatch({
          type: "APPEND_PRD",
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
      ctx.dispatch({
        type: "ADD_MESSAGE",
        message: {
          data_product_id: "live",
          step: ctx.currentStep,
          message_role: "agent",
          message_text: `⚠️ ${event.code}: ${event.message}`,
          timestamp: new Date().toISOString(),
        } as any,
      });
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
    const headers: Record<string, string> = { "X-DSA-Session-ID": sessionId };
    if (isAuthEnabled()) {
      const idToken = getIdToken();
      if (idToken) headers.Authorization = `Bearer ${idToken}`;
    }
    const response = await fetch(`${BACKEND_URL}${downloadUrl}`, {
      method: "GET",
      headers,
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
