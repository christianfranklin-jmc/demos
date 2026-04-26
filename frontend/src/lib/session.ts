// Per-tab session identifier. See docs/adr/015-dsa-agent-integration.md D6.
// Minted on first access in a tab; stored in sessionStorage so refresh
// preserves it but tab close discards it. AgentCore Memory records are
// keyed on this ID (via the X-DSA-Session-ID header).

const KEY = "dsa_session_id";

let cache: string | null = null;

/** Return the current tab's session ID, minting one on first call. */
export function getOrMintSessionId(): string {
  if (cache) return cache;
  const existing = safeRead();
  if (existing) {
    cache = existing;
    return existing;
  }
  const fresh = mintUuid();
  safeWrite(fresh);
  cache = fresh;
  return fresh;
}

/** Return the stored session ID without minting one. Null if empty. */
export function currentSessionId(): string | null {
  if (cache) return cache;
  const existing = safeRead();
  if (existing) cache = existing;
  return cache;
}

/**
 * Per-tab Workspace ID — same value as the session ID (002-dsa-hub-pinnacle Q1).
 * Exposed under a workspace-shaped name so callers that have switched to the
 * Workspace abstraction can read a more semantically accurate identifier
 * without a separate UUID. Backend accepts either header (FR-006).
 */
export function getOrMintWorkspaceId(): string {
  return getOrMintSessionId();
}

/** Clear the current session ID. Used only by an explicit "Start new session" UI (not wired in this release). */
export function clearSession(): void {
  cache = null;
  if (typeof sessionStorage !== "undefined") {
    sessionStorage.removeItem(KEY);
  }
}

function mintUuid(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  // Vitest/jsdom fallback — RFC4122 v4 pattern, not cryptographically strong.
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === "x" ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

function safeRead(): string | null {
  try {
    if (typeof sessionStorage === "undefined") return null;
    return sessionStorage.getItem(KEY);
  } catch {
    return null;
  }
}

function safeWrite(value: string): void {
  try {
    if (typeof sessionStorage !== "undefined") sessionStorage.setItem(KEY, value);
  } catch {
    /* ignore — private-mode Safari can throw */
  }
}
