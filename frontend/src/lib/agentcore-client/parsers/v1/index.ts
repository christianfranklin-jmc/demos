// SSE event schema v1 parser — mirrors src/platform_agent/api/events.py.
// See contracts/sse-events.md for the wire format and ADR-015 D14 for rationale.

import type { SSEEventV1 } from "../../../types";

const TERMINAL_EVENTS = new Set<SSEEventV1["event"]>(["done", "error", "artifact_ready"]);

/** Raw SSE frame after the parser has split on blank lines. */
interface RawFrame {
  event: string;
  data: string;
}

export class SSEParseError extends Error {}

/** Parse a raw SSE text buffer into an iterable of {event, data} frames. */
export function* splitFrames(chunk: string): Generator<RawFrame> {
  // Buffer splitting done by the caller; this yields only complete frames.
  const blocks = chunk.split(/\n\n/);
  for (const block of blocks) {
    if (!block.trim()) continue;
    let event = "message";
    const dataLines: string[] = [];
    for (const line of block.split(/\n/)) {
      if (line.startsWith("event:")) {
        event = line.slice(6).trim();
      } else if (line.startsWith("data:")) {
        dataLines.push(line.slice(5).trimStart());
      }
    }
    yield { event, data: dataLines.join("\n") };
  }
}

/** Parse a single raw frame into a typed event. Throws SSEParseError on failure. */
export function parseFrame(frame: RawFrame): SSEEventV1 {
  let payload: Record<string, unknown>;
  try {
    payload = JSON.parse(frame.data) as Record<string, unknown>;
  } catch (cause) {
    throw new SSEParseError(`Invalid JSON in ${frame.event} event: ${String(cause)}`);
  }
  if (payload.v !== 1) {
    throw new SSEParseError(`Unsupported schema version ${String(payload.v)} in ${frame.event}`);
  }
  // Structural validation is per-shape; we trust the discriminator `event` channel.
  return { event: frame.event as SSEEventV1["event"], ...payload } as SSEEventV1;
}

/** True if the event closes the stream. */
export function isTerminal(event: SSEEventV1): boolean {
  return TERMINAL_EVENTS.has(event.event);
}

/**
 * A 30-second silence timer that fires if no event arrives.
 * Callers invoke `.bump()` on every event to reset; `.dispose()` on stream end.
 *
 * Threshold matches FR-023 / Clarify Q5: 30 seconds of silence = failure.
 */
export class SilenceTimer {
  private handle: ReturnType<typeof setTimeout> | null = null;

  constructor(
    private readonly onTimeout: () => void,
    private readonly thresholdMs = 30_000,
  ) {
    this.bump();
  }

  bump(): void {
    if (this.handle !== null) clearTimeout(this.handle);
    this.handle = setTimeout(this.onTimeout, this.thresholdMs);
  }

  dispose(): void {
    if (this.handle !== null) {
      clearTimeout(this.handle);
      this.handle = null;
    }
  }
}

/**
 * Stream a fetch Response body as typed v1 SSE events.
 * Yields each parsed event. Caller handles terminal events (error/done/artifact_ready)
 * and disposes the silence timer appropriately.
 */
export async function* streamEvents(
  response: Response,
  silenceTimer?: SilenceTimer,
): AsyncGenerator<SSEEventV1> {
  if (!response.body) throw new SSEParseError("Response has no body");
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      // Split on frame boundary (\n\n), keep trailing partial in buffer.
      const parts = buffer.split(/\n\n/);
      buffer = parts.pop() ?? "";
      for (const block of parts) {
        if (!block.trim()) continue;
        for (const frame of splitFrames(block + "\n\n")) {
          const evt = parseFrame(frame);
          silenceTimer?.bump();
          yield evt;
          if (isTerminal(evt)) return;
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}
