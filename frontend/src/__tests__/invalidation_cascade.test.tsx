// T029a: FR-010 cascading gate invalidation unit test.
//
// Exercises WORKFLOW_INVALIDATE_DOWNSTREAM directly against the reducer
// rather than through React — the reducer is pure, so a unit test on it
// covers the cascade logic without needing jsdom / testing-library here.

import { describe, expect, it } from "vitest";

// We re-import the reducer via a module boundary that exports it for testing.
// AppContext currently only exports the Provider; this file asserts the
// contract from the outside by driving actions through the public hook API,
// so we construct a tiny in-test reducer harness.

import { act, renderHook } from "@testing-library/react";

// NOTE: extract the reducer and initialState to a module test helper in T041+
// if unit tests proliferate. For now, re-create the minimum reducer shape we
// need by invoking through AppProvider and reading state via useAppState.
// Kept minimal to avoid importing React context that pulls in Vite env vars.

import { AppProvider, useAppState } from "../context/AppContext";

function wrapper({ children }: { children: React.ReactNode }) {
  return <AppProvider>{children}</AppProvider>;
}

describe("WORKFLOW_INVALIDATE_DOWNSTREAM", () => {
  it("clears artifacts strictly after fromStep and preserves earlier state", () => {
    const { result } = renderHook(() => useAppState(), { wrapper });

    // Approve Steps 1, 2, 3.
    act(() => {
      result.current.dispatch({ type: "APPROVE_GATE", step: 1, approvedBy: "tester" });
    });
    act(() => {
      result.current.dispatch({ type: "APPROVE_GATE", step: 2, approvedBy: "tester" });
    });
    act(() => {
      result.current.dispatch({ type: "APPROVE_GATE", step: 3, approvedBy: "tester" });
    });

    // Place some sample artifacts so we can assert they are cleared.
    act(() => {
      result.current.dispatch({
        type: "SET_CONCEPTUAL_MODEL",
        model: { entities: [], relationships: [] } as any,
      });
      result.current.dispatch({
        type: "SET_LOGICAL_MODEL",
        model: { entities: [] } as any,
      });
      result.current.dispatch({
        type: "SET_DETAILED_REQUIREMENTS",
        model: { fact_table: null, dimension_tables: [] } as any,
      });
    });

    // Re-run Step 2 — should invalidate Steps 3 and 4.
    act(() => {
      result.current.dispatch({ type: "WORKFLOW_INVALIDATE_DOWNSTREAM", fromStep: 2 });
    });

    const s = result.current.state;
    expect(s.lifecycle.current_step).toBe(2);
    expect(s.lifecycle.approved_steps.includes(3)).toBe(false);
    expect(s.lifecycle.approved_steps.includes(1)).toBe(true);
    expect(s.lifecycle.step_statuses[3]).toBe("not_started");
    expect(s.lifecycle.step_statuses[4]).toBe("not_started");
    // Step 2 itself is preserved.
    expect(s.lifecycle.step_statuses[2]).toBe("approved");
    // Downstream artifacts cleared; conceptual (Step 2) preserved.
    expect(s.artifacts.conceptual).not.toBeNull();
    expect(s.artifacts.logical).toBeNull();
    expect(s.artifacts.detailed).toBeNull();
  });

  it("re-run from Step 1 clears every downstream step and artifact", () => {
    const { result } = renderHook(() => useAppState(), { wrapper });

    act(() => {
      result.current.dispatch({ type: "APPROVE_GATE", step: 1, approvedBy: "tester" });
      result.current.dispatch({ type: "APPROVE_GATE", step: 2, approvedBy: "tester" });
      result.current.dispatch({ type: "APPROVE_GATE", step: 3, approvedBy: "tester" });
    });
    act(() => {
      result.current.dispatch({
        type: "SET_CONCEPTUAL_MODEL",
        model: { entities: [], relationships: [] } as any,
      });
      result.current.dispatch({
        type: "SET_LOGICAL_MODEL",
        model: { entities: [] } as any,
      });
    });

    act(() => {
      result.current.dispatch({ type: "WORKFLOW_INVALIDATE_DOWNSTREAM", fromStep: 1 });
    });

    const s = result.current.state;
    expect(s.artifacts.conceptual).toBeNull();
    expect(s.artifacts.logical).toBeNull();
    expect(s.artifacts.detailed).toBeNull();
    expect(s.lifecycle.current_step).toBe(1);
    expect(s.lifecycle.approved_steps).toEqual([1]);
  });
});
