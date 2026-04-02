// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: Apache-2.0

/** Supported agent pattern prefixes — determines the frontend parser */
export type AgentPattern =
  | `agui-${string}`
  | `strands-${string}`
  | `langgraph-${string}`
  | `claude-${string}`

/** Configuration for AgentCoreClient */
export interface AgentCoreConfig {
  runtimeArn: string
  region?: string
  pattern: AgentPattern
}

/** Stream event types emitted by parsers */
export type StreamEvent =
  | { type: "text"; content: string }
  | { type: "tool_use_start"; toolUseId: string; name: string }
  | { type: "tool_use_delta"; toolUseId: string; input: string }
  | { type: "tool_result"; toolUseId: string; result: string }
  | { type: "message"; role: string; content: unknown[] }
  | { type: "result"; stopReason: string }
  | { type: "lifecycle"; event: string }

/** Callback invoked with each stream event */
export type StreamCallback = (event: StreamEvent) => void

/** Parses a single SSE line and emits events via callback */
export type ChunkParser = (line: string, callback: StreamCallback) => void

// --- Project-specific types (Platform Agent) ---

export interface AgentMessage {
  role: 'user' | 'assistant' | 'system'
  content: string
  timestamp?: string
}

export interface AgentSession {
  sessionId: string
  messages: AgentMessage[]
}

export interface QueryResult {
  columns: string[]
  rows: Record<string, unknown>[]
  rowCount: number
  truncated: boolean
}

export interface SchemaInfo {
  sourceId: string
  database: string
  schema: string
  tables: TableInfo[]
}

export interface TableInfo {
  tableName: string
  columns: ColumnInfo[]
  primaryKey: string[]
  foreignKeys: ForeignKeyInfo[]
  rowCount: number
}

export interface ColumnInfo {
  columnName: string
  dataType: string
  isNullable: string
  ordinalPosition: number
}

export interface ForeignKeyInfo {
  sourceTable: string
  sourceColumn: string
  targetTable: string
  targetColumn: string
}
