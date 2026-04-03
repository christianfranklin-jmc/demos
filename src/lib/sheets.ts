/**
 * Persistent Layer — Google Sheets API
 *
 * For the MVP demo, state can run entirely in-memory via AppContext.
 * This module provides the read/write interface for when Google Sheets
 * is connected. Schema matches target Snowflake structure exactly.
 *
 * 5 sheets (one per table):
 *   1. lifecycle_state
 *   2. artifact_log
 *   3. approval_audit
 *   4. agent_conversation_log
 *   5. quality_flags
 */

import type {
  LifecycleState,
  ArtifactLog,
  ApprovalAudit,
  ConversationMessage,
  QualityFlag,
} from "./types";

const SHEETS_ID = import.meta.env.VITE_GOOGLE_SHEETS_ID;
const API_KEY = import.meta.env.VITE_GOOGLE_API_KEY;
const BASE_URL = `https://sheets.googleapis.com/v4/spreadsheets/${SHEETS_ID}`;

/**
 * Check if Google Sheets is configured.
 * If not, the app runs in local-only mode.
 */
export function isSheetsConfigured(): boolean {
  return Boolean(SHEETS_ID && API_KEY);
}

/**
 * Read lifecycle state for a data product.
 */
export async function readLifecycleState(
  dataProductId: string
): Promise<LifecycleState | null> {
  if (!isSheetsConfigured()) return null;

  try {
    const response = await fetch(
      `${BASE_URL}/values/lifecycle_state!A:Z?key=${API_KEY}`
    );
    const data = await response.json();
    // TODO: Parse rows into LifecycleState, filter by dataProductId
    console.log("Sheets lifecycle_state:", data);
    return null; // Implement parsing
  } catch (error) {
    console.error("Failed to read lifecycle state from Sheets:", error);
    return null;
  }
}

/**
 * Write a lifecycle state update.
 */
export async function writeLifecycleState(
  state: LifecycleState
): Promise<void> {
  if (!isSheetsConfigured()) return;
  // TODO: Implement Sheets API write
  console.log("Would write lifecycle state:", state);
}

/**
 * Append a conversation message.
 */
export async function appendConversationMessage(
  message: ConversationMessage
): Promise<void> {
  if (!isSheetsConfigured()) return;
  // TODO: Implement Sheets API append
  console.log("Would append message:", message);
}

/**
 * Write an artifact log entry.
 */
export async function writeArtifactLog(entry: ArtifactLog): Promise<void> {
  if (!isSheetsConfigured()) return;
  console.log("Would write artifact log:", entry);
}

/**
 * Write an approval audit entry.
 */
export async function writeApprovalAudit(
  entry: ApprovalAudit
): Promise<void> {
  if (!isSheetsConfigured()) return;
  console.log("Would write approval audit:", entry);
}

/**
 * Write a quality flag.
 */
export async function writeQualityFlag(flag: QualityFlag): Promise<void> {
  if (!isSheetsConfigured()) return;
  console.log("Would write quality flag:", flag);
}
