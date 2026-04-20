// Demo-mode dispatcher.
//
// The pre-scripted conversation engine lives in hooks/useAgent.demo.ts. It
// watches AppContext.demoMode.enabled and drives the same reducer actions
// a live backend call would (ADD_MESSAGE, UPDATE_PRD, SET_CONCEPTUAL_MODEL,
// SET_LOGICAL_MODEL, SET_DETAILED_REQUIREMENTS). Because it is stateful and
// watches all four steps, no separate stateless `resolveStep()` function is
// needed — useAgent conditionally delegates to the demo engine based on
// AppContext.demoMode.enabled.
//
// This module exists for two things:
//   1. Document the architecture (ADR-015 D13: demo mode is frontend-only).
//   2. Expose a small helper to flip demo mode on/off from any component.
//
// Keep this module stateless; all state lives in AppContext.demoMode.

import type { AppDispatch } from "../context/AppContext";

/**
 * Enable demo mode with a visible reason stamp. The pre-scripted engine
 * (useAgent.demo.ts) takes over message dispatch once this flips.
 */
export function enableDemoMode(dispatch: AppDispatch, reason: "user_toggle" | "auto_fallback"): void {
  if (reason === "auto_fallback") {
    dispatch({ type: "DEMO_MODE_AUTO_ENABLE" });
  } else {
    dispatch({ type: "DEMO_MODE_ENABLE" });
  }
}

export function disableDemoMode(dispatch: AppDispatch): void {
  dispatch({ type: "DEMO_MODE_DISABLE" });
}
