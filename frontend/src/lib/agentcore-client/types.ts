/**
 * Type definitions for AgentCore client.
 * Based on FAST template: frontend/src/lib/agentcore-client/types.ts
 */

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
