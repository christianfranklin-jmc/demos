// SSE event schema v2 parser (T087, US3).
//
// Mirrors src/platform_agent/provisioning/events.py. Every v2 event carries
// a {run_id, seq, ts, v: 2, kind} envelope plus kind-specific payload.
// The parser exposes typed unions so consumers (useProvisioningRun) can
// switch on `kind` exhaustively.
//
// v2 is additive over v1 — see ../v1/ for the legacy events used by the
// step workflow. Both parsers share the same EventSource/fetch transport.

// ───── Domain types (mirror provisioning/models.py) ─────

export type AgentId =
  | "schema"
  | "pipeline"
  | "model"
  | "quality"
  | "mapping"
  | "semantic"
  | "delivery";

export type AgentState =
  | "pending"
  | "active"
  | "completed"
  | "failed"
  | "retrying";

export interface KpiTick {
  ts: string;
  rows_in_motion: number;
  agents_active: number;
  files_written: number;
  latency_ms_p95: number | null;
  est_cost_usd: number | null;
  eta_seconds: number | null;
}

export interface ArtifactRef {
  kind: string;
  ref: string;
  meta?: Record<string, unknown>;
}

// ───── Event types ─────

interface V2Envelope {
  v: 2;
  run_id: string;
  seq: number;
  ts: string;
}

export interface AgentStartedEventV2 extends V2Envelope {
  kind: "agent.started";
  agent_id: AgentId;
  attempt: number;
}

export interface AgentProgressEventV2 extends V2Envelope {
  kind: "agent.progress";
  agent_id: AgentId;
  message: string;
}

export interface AgentCompletedEventV2 extends V2Envelope {
  kind: "agent.completed";
  agent_id: AgentId;
  artifacts: ArtifactRef[];
  latency_ms_p95: number | null;
}

export interface AgentFailedEventV2 extends V2Envelope {
  kind: "agent.failed";
  agent_id: AgentId;
  error_code: string;
  error_message: string;
  retryable: boolean;
}

export interface KpiTickEventV2 extends V2Envelope {
  kind: "kpi.tick";
  tick: KpiTick;
}

export interface ArtifactProducedEventV2 extends V2Envelope {
  kind: "artifact.produced";
  agent_id: AgentId;
  artifact: ArtifactRef;
}

export interface ValidationStartedEventV2 extends V2Envelope {
  kind: "validation.started";
  question_count: number;
}

export interface ValidationResultEventV2 extends V2Envelope {
  kind: "validation.result";
  question: string;
  state: "passed" | "failed";
  sql_executed: string | null;
  latency_ms: number | null;
  judge_reasoning: string;
}

export interface RunCompletedEventV2 extends V2Envelope {
  kind: "run.completed";
  product_id: string;
  product_state: "final" | "provisional";
  validation_pass_rate: number;
}

export interface RunNeedsReplanEventV2 extends V2Envelope {
  kind: "run.needs_replan";
  reason: string;
  suggested_agent: AgentId | null;
}

export interface HeartbeatEventV2 extends V2Envelope {
  kind: "heartbeat";
}

export type ProvisionEventV2 =
  | AgentStartedEventV2
  | AgentProgressEventV2
  | AgentCompletedEventV2
  | AgentFailedEventV2
  | KpiTickEventV2
  | ArtifactProducedEventV2
  | ValidationStartedEventV2
  | ValidationResultEventV2
  | RunCompletedEventV2
  | RunNeedsReplanEventV2
  | HeartbeatEventV2;

// ───── Parser ─────

export class SSEv2ParseError extends Error {}

interface RawSSEFrame {
  event: string;
  data: string;
}

/** Split an SSE buffer into complete `{event, data}` frames. */
export function* splitFrames(chunk: string): Generator<RawSSEFrame> {
  const blocks = chunk.split(/\n\n/);
  for (const block of blocks) {
    if (!block.trim()) continue;
    let event = "message";
    const dataLines: string[] = [];
    for (const line of block.split("\n")) {
      if (line.startsWith("event:")) event = line.slice(6).trim();
      else if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
    }
    yield { event, data: dataLines.join("\n") };
  }
}

/** Parse a single raw frame into a typed v2 event. */
export function parseFrame(frame: RawSSEFrame): ProvisionEventV2 {
  let payload: unknown;
  try {
    payload = JSON.parse(frame.data || "{}");
  } catch (exc) {
    throw new SSEv2ParseError(`bad JSON in frame ${frame.event}: ${exc}`);
  }
  if (typeof payload !== "object" || payload === null) {
    throw new SSEv2ParseError(`frame ${frame.event} payload is not an object`);
  }
  const obj = payload as Record<string, unknown>;
  // Heartbeat frames carry an empty `{}` body — synthesize the kind.
  if (frame.event === "heartbeat" && !obj.kind) {
    obj.kind = "heartbeat";
    obj.v = 2;
    obj.run_id = (obj.run_id as string) ?? "";
    obj.seq = (obj.seq as number) ?? 0;
    obj.ts = (obj.ts as string) ?? new Date().toISOString();
  }
  if (obj.v !== 2) {
    throw new SSEv2ParseError(`frame ${frame.event} is not v2 (v=${obj.v})`);
  }
  return obj as unknown as ProvisionEventV2;
}

/** Open an SSE stream against `url` and yield typed events until close. */
export async function* streamEvents(
  url: string,
  init: RequestInit & { signal?: AbortSignal }
): AsyncGenerator<ProvisionEventV2> {
  const response = await fetch(url, { ...init, headers: { ...init.headers } });
  if (!response.ok || !response.body) {
    throw new SSEv2ParseError(`SSE open failed: HTTP ${response.status}`);
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";
  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      // Process every complete frame in the buffer; keep the trailing partial.
      const lastBoundary = buffer.lastIndexOf("\n\n");
      if (lastBoundary < 0) continue;
      const ready = buffer.slice(0, lastBoundary + 2);
      buffer = buffer.slice(lastBoundary + 2);
      for (const frame of splitFrames(ready)) {
        try {
          yield parseFrame(frame);
        } catch (exc) {
          // Log + skip — never break the stream on a single bad frame.
          // eslint-disable-next-line no-console
          console.warn("[v2 parser]", exc);
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}
