// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: Apache-2.0

import type { ChunkParser } from "../types"

/**
 * Parses SSE chunks from Strands agents.
 * Emits typed StreamEvents for text, tool use, messages, and lifecycle.
 */
export const parseStrandsChunk: ChunkParser = (line, callback) => {
  if (!line.startsWith("data: ")) return

  const data = line.substring(6).trim()
  if (!data) return

  try {
    const json = JSON.parse(data)

    // Converse-format events (from BedrockAgentCoreApp)
    if (json.event) {
      const event = json.event
      if (event.contentBlockDelta?.delta?.text) {
        callback({ type: "text", content: event.contentBlockDelta.delta.text })
        return
      }
      if (event.contentBlockStart?.start?.toolUse) {
        const toolUse = event.contentBlockStart.start.toolUse
        callback({
          type: "tool_use_start",
          toolUseId: toolUse.toolUseId,
          name: toolUse.name,
        })
        return
      }
      if (event.contentBlockDelta?.delta?.toolUse?.input) {
        callback({
          type: "tool_use_delta",
          toolUseId: "",
          input: event.contentBlockDelta.delta.toolUse.input,
        })
        return
      }
      if (event.messageStop?.stopReason) {
        callback({ type: "result", stopReason: event.messageStop.stopReason })
        return
      }
      if (event.messageStart) {
        callback({ type: "lifecycle", event: "message_start" })
        return
      }
      return
    }

    // Text streaming (Strands high-level format)
    if (typeof json.data === "string") {
      callback({ type: "text", content: json.data })
      return
    }

    // Tool use streaming
    if (json.current_tool_use) {
      const tool = json.current_tool_use
      // First delta for a tool has empty input — treat as start
      if (json.delta?.toolUse?.input === "") {
        callback({
          type: "tool_use_start",
          toolUseId: tool.toolUseId,
          name: tool.name,
        })
      } else if (json.delta?.toolUse?.input) {
        callback({
          type: "tool_use_delta",
          toolUseId: tool.toolUseId,
          input: json.delta.toolUse.input,
        })
      }
      return
    }

    // Complete message (assistant with toolUse, or user with toolResult)
    if (json.message) {
      const msg = json.message
      callback({ type: "message", role: msg.role, content: msg.content })

      // Extract tool results from user messages
      if (msg.role === "user" && Array.isArray(msg.content)) {
        for (const block of msg.content) {
          if (block.toolResult) {
            const resultText =
              block.toolResult.content
                ?.map((c: { text?: string }) => c.text)
                .filter(Boolean)
                .join("") || JSON.stringify(block.toolResult.content)
            callback({
              type: "tool_result",
              toolUseId: block.toolResult.toolUseId,
              result: resultText,
            })
          }
        }
      }
      return
    }

    // Final result
    if (json.result) {
      callback({
        type: "result",
        stopReason: typeof json.result === "object" ? json.result.stop_reason : "end_turn",
      })
      return
    }

    // Lifecycle events
    if (json.init_event_loop || json.start_event_loop || json.start) {
      const event = json.init_event_loop ? "init" : json.start_event_loop ? "start_loop" : "start"
      callback({ type: "lifecycle", event })
      return
    }
  } catch {
    console.debug("Failed to parse strands event:", data)
  }
}
