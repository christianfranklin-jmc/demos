// T046: Cancel button shown while an agent run is in flight.
//
// Mount beside the ChatInput. Uses the module-level controller exposed by
// useAgent so the cancel signal aborts the outstanding fetch and tells the
// backend via POST /workflow/cancel.

import { useAppState } from "../../context/AppContext";
import { useTheme } from "../../context/ThemeContext";
import { getCurrentRun } from "../../hooks/useAgent";

const BACKEND_URL =
  (import.meta as any).env?.VITE_BACKEND_URL ?? "http://localhost:8080";

export default function CancelButton() {
  const { state } = useAppState();
  const { theme } = useTheme();

  if (!state.ui.isAgentThinking) return null;

  const handleCancel = async () => {
    const run = getCurrentRun();
    if (!run) return;
    run.abort();
    if (!run.runId) return;
    try {
      await fetch(`${BACKEND_URL}/workflow/cancel`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-DSA-Session-ID": state.sessionId,
        },
        body: JSON.stringify({ session_id: state.sessionId, run_id: run.runId }),
      });
    } catch (err) {
      console.warn("cancel notification failed (client-side abort already sent):", err);
    }
  };

  return (
    <button
      type="button"
      onClick={handleCancel}
      className="px-3 py-1.5 text-xs rounded"
      style={{
        background: theme.colors.surfaceInput,
        color: theme.colors.textPrimary,
        border: `1px solid ${theme.colors.borderSubtle}`,
      }}
      title="Abort the in-flight agent run"
    >
      Cancel
    </button>
  );
}
