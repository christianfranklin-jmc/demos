// 002-dsa-hub-pinnacle US3 — v2 SSE parser unit tests.
//
// Verifies the parser end of the contract that the backend integration
// tests cover from the producer side. Asserts envelope shape, frame
// splitting on `\n\n`, kind-discriminated parsing, and graceful
// recovery on malformed frames.

import { describe, expect, it } from "vitest";
import { parseFrame, splitFrames } from "../lib/agentcore-client/parsers/v2";

describe("splitFrames", () => {
  it("splits buffered SSE frames on blank-line boundaries", () => {
    const buf =
      "event: agent.started\ndata: {\"v\":2,\"run_id\":\"r1\",\"seq\":1,\"ts\":\"t\",\"kind\":\"agent.started\",\"agent_id\":\"schema\",\"attempt\":1}\n\n" +
      "event: kpi.tick\ndata: {\"v\":2,\"run_id\":\"r1\",\"seq\":2,\"ts\":\"t\",\"kind\":\"kpi.tick\",\"tick\":{\"ts\":\"t\",\"rows_in_motion\":0,\"agents_active\":1,\"files_written\":0,\"latency_ms_p95\":null,\"est_cost_usd\":null,\"eta_seconds\":null}}\n\n";
    const frames = Array.from(splitFrames(buf));
    expect(frames).toHaveLength(2);
    expect(frames[0].event).toBe("agent.started");
    expect(frames[1].event).toBe("kpi.tick");
  });

  it("ignores blank/whitespace blocks", () => {
    const frames = Array.from(splitFrames("\n\n   \n\n"));
    expect(frames).toHaveLength(0);
  });
});

describe("parseFrame", () => {
  it("parses an agent.completed envelope", () => {
    const frame = {
      event: "agent.completed",
      data: JSON.stringify({
        v: 2,
        run_id: "r1",
        seq: 5,
        ts: "2026-04-26T08:00:00Z",
        kind: "agent.completed",
        agent_id: "mapping",
        artifacts: [{ kind: "iceberg_table", ref: "iceberg.x.y" }],
        latency_ms_p95: 42,
      }),
    };
    const ev = parseFrame(frame);
    expect(ev.kind).toBe("agent.completed");
    if (ev.kind === "agent.completed") {
      expect(ev.agent_id).toBe("mapping");
      expect(ev.artifacts).toHaveLength(1);
    }
  });

  it("synthesizes heartbeat envelope from empty body", () => {
    const ev = parseFrame({ event: "heartbeat", data: "{}" });
    expect(ev.kind).toBe("heartbeat");
    expect(ev.v).toBe(2);
  });

  it("rejects non-v2 frames", () => {
    expect(() =>
      parseFrame({
        event: "x",
        data: JSON.stringify({ v: 1, run_id: "r", seq: 0, ts: "t", kind: "x" }),
      })
    ).toThrow();
  });

  it("rejects malformed JSON", () => {
    expect(() => parseFrame({ event: "x", data: "{ not json" })).toThrow();
  });
});
