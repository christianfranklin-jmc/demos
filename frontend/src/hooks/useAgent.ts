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
} from "../lib/types";
import {
  SilenceTimer,
  streamEvents,
} from "../lib/agentcore-client/parsers/v1";

const BACKEND_URL =
  (import.meta as any).env?.VITE_BACKEND_URL ?? "http://localhost:8080";

export interface RunStepController {
  abort: () => void;
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

    return () => {
      inFlightRef.current?.abort();
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
  const body: StepRequest = {
    step_id: stepId,
    user_message: userMessage,
    prior_artifact: null, // T041-T044 populate this from AppContext
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

      silence = new SilenceTimer(() => {
        abortCtl.abort(new DOMException("Silence timeout", "TimeoutError"));
      });

      for await (const event of streamEvents(response, silence)) {
        handleEvent(event, ctx);
      }
    } catch (err) {
      if (abortCtl.signal.aborted) return; // caller-initiated abort is clean
      const message = err instanceof Error ? err.message : String(err);
      // TODO(T064): offer "Continue in demo mode" affordance on error.
      // TODO(T025d): when err came from a MemoryUnavailable, also dispatch
      //              MEMORY_STATUS_SET here. Requires parsing ErrorEvent.code.
      console.error("runStep error:", message);
    } finally {
      silence?.dispose();
      ctx.dispatch({ type: "SET_AGENT_THINKING", thinking: false });
    }
  })();

  return { abort: () => abortCtl.abort() };
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
      // TODO(T046): wire into a progress pane. For now, informational only.
      return;

    case "message":
      // TODO(T041+): accumulate streamed assistant messages. For the shell, we
      // leave the conversation unchanged — user-visible chat updates land with
      // each step's renderer.
      return;

    case "artifact_update":
      // TODO(T041-T043): dispatch per-step reducer actions:
      //   prd              → UPDATE_PRD
      //   conceptual_model → SET_CONCEPTUAL_MODEL
      //   logical_model    → SET_LOGICAL_MODEL
      return;

    case "artifact_ready":
      // TODO(T044): fetch /workflow/artifact/{handle} and trigger download.
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
