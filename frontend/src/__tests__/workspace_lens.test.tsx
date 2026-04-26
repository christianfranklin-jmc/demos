// 002-dsa-hub-pinnacle US1 — workspace state machine + lens helpers.
//
// Drives WORKSPACE_CONNECTIONS_SET and LENS_SET through the AppContext
// reducer to assert:
// - Setting connections updates state.
// - Setting an active lens whose connection is later removed falls back
//   to "all" (defensive auto-correction).
// - deriveLensOptions yields the expected shape (only ≥2 live → "All").

import { describe, expect, it } from "vitest";
import { act, renderHook } from "@testing-library/react";

import {
  AppProvider,
  deriveLensOptions,
  useAppState,
  type WorkspaceConnectionRef,
} from "../context/AppContext";

function wrapper({ children }: { children: React.ReactNode }) {
  return <AppProvider>{children}</AppProvider>;
}

const PG: WorkspaceConnectionRef = {
  connection_id: "abc",
  driver_type: "postgresql",
  display_name: "Pinnacle PG",
  scope: "pinnacle.public",
  status: "live",
};
const SF: WorkspaceConnectionRef = {
  connection_id: "def",
  driver_type: "snowflake",
  display_name: "Pinnacle SF",
  scope: "PINNACLE_FINANCIAL_DEMO_ASINGH.ANALYTICS",
  status: "live",
};
const ICEBERG_CONNECTING: WorkspaceConnectionRef = {
  connection_id: "ghi",
  driver_type: "iceberg",
  display_name: "Iceberg",
  scope: "dsa_hub_pinnacle_360",
  status: "connecting",
};

describe("deriveLensOptions", () => {
  it("returns no options when zero live connections", () => {
    expect(deriveLensOptions([])).toEqual([]);
    expect(deriveLensOptions([ICEBERG_CONNECTING])).toEqual([]);
  });

  it("returns one entry without 'All' when exactly one live connection", () => {
    const opts = deriveLensOptions([PG]);
    expect(opts).toHaveLength(1);
    expect(opts[0].kind).toBe("connection");
  });

  it("includes 'All sources' as the first option once ≥2 live connections", () => {
    const opts = deriveLensOptions([PG, SF, ICEBERG_CONNECTING]);
    expect(opts).toHaveLength(3); // All + PG + SF (Iceberg is connecting, excluded)
    expect(opts[0].kind).toBe("all");
    expect(opts[0].label).toBe("All sources");
  });
});

describe("WORKSPACE_CONNECTIONS_SET + LENS_SET", () => {
  it("updates workspaceConnections + activeLens", () => {
    const { result } = renderHook(() => useAppState(), { wrapper });
    act(() => {
      result.current.dispatch({
        type: "WORKSPACE_CONNECTIONS_SET",
        connections: [PG, SF],
      });
    });
    expect(result.current.state.workspaceConnections).toHaveLength(2);
    act(() => {
      result.current.dispatch({
        type: "LENS_SET",
        lens: { kind: "connection", connection_id: "abc" },
      });
    });
    expect(result.current.state.activeLens).toEqual({
      kind: "connection",
      connection_id: "abc",
    });
  });

  it("falls back to 'all' when the active lens's connection is removed", () => {
    const { result } = renderHook(() => useAppState(), { wrapper });
    act(() => {
      result.current.dispatch({
        type: "WORKSPACE_CONNECTIONS_SET",
        connections: [PG, SF],
      });
    });
    act(() => {
      result.current.dispatch({
        type: "LENS_SET",
        lens: { kind: "connection", connection_id: "def" },
      });
    });
    // Now drop SF (connection_id "def").
    act(() => {
      result.current.dispatch({
        type: "WORKSPACE_CONNECTIONS_SET",
        connections: [PG],
      });
    });
    expect(result.current.state.activeLens).toEqual({ kind: "all" });
  });
});
