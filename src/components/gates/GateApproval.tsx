/**
 * GateApproval — Inline approval section at bottom of artifact panel.
 * User must scroll to reach it. Replaces the old fixed bottom banner.
 */

import { useState } from "react";
import { useAppState } from "../../context/AppContext";
import { useTheme } from "../../context/ThemeContext";
import { getStepConfig, getGateConfig } from "../../lib/constants";
import type { StepNumber } from "../../lib/types";

export default function GateApproval() {
  const { state, dispatch } = useAppState();
  const { theme } = useTheme();
  const currentStep = state.lifecycle.current_step;
  const stepConfig = getStepConfig(currentStep);
  const gateConfig = getGateConfig(currentStep);
  const [requestingChanges, setRequestingChanges] = useState(false);
  const [changeNote, setChangeNote] = useState("");
  const [approved, setApproved] = useState(false);

  if (!state.ui.gateActive || !stepConfig.gate_name || !gateConfig) return null;

  const handleApprove = () => {
    setApproved(true);
    setTimeout(() => {
      dispatch({
        type: "APPROVE_GATE",
        step: currentStep as StepNumber,
        approvedBy: gateConfig.approver_description,
      });
      // Reset the active tab for the next step
      const nextStep = currentStep + 1;
      if (nextStep <= 4) {
        const nextConfig = getStepConfig(nextStep as StepNumber);
        dispatch({ type: "SET_ACTIVE_TAB", tab: nextConfig.tab_name });
      }
      setApproved(false);
    }, 800);
  };

  const handleRequestChanges = () => {
    if (requestingChanges && changeNote.trim()) {
      // Send the note as a user message, deactivate gate, agent will respond
      dispatch({
        type: "ADD_MESSAGE",
        message: {
          data_product_id: state.lifecycle.data_product_id,
          step: currentStep as StepNumber,
          message_role: "user",
          message_text: `[Change Request] ${changeNote.trim()}`,
          timestamp: new Date().toISOString(),
        },
      });
      dispatch({ type: "SET_GATE_ACTIVE", active: false });
      setRequestingChanges(false);
      setChangeNote("");
    } else {
      setRequestingChanges(true);
    }
  };

  return (
    <div
      className="mx-4 mb-6 mt-8 rounded-lg border"
      style={{
        borderColor: theme.colors.borderSubtle,
        backgroundColor: theme.colors.surfaceSubtle,
      }}
    >
      {/* Gate header */}
      <div className="px-5 py-4">
        <div className="flex items-center gap-2 mb-1">
          <span style={{ color: theme.colors.textPrimary, fontSize: "14px" }}>&#128737;</span>
          <p
            className="text-xs font-bold uppercase tracking-wide"
            style={{ color: theme.colors.textPrimary }}
          >
            Human Gate &middot; {stepConfig.gate_name}
          </p>
        </div>
        <p className="text-xs ml-6" style={{ color: theme.colors.textSecondary }}>
          {gateConfig.approver_description}
        </p>

        {/* Open flags warning */}
        {state.flags.filter((f) => f.status === "open" && f.step === currentStep).length > 0 && (
          <div
            className="mt-3 ml-6 px-3 py-2 rounded text-xs"
            style={{
              backgroundColor: theme.colors.flagAmberSurface || "#FEF3C7",
              color: theme.colors.flagAmber,
            }}
          >
            {state.flags.filter((f) => f.status === "open" && f.step === currentStep).length} open flag(s) — review before approving
          </div>
        )}
      </div>

      {/* Request changes inline input */}
      {requestingChanges && (
        <div className="px-5 pb-3">
          <input
            type="text"
            autoFocus
            value={changeNote}
            onChange={(e) => setChangeNote(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") handleRequestChanges();
              if (e.key === "Escape") setRequestingChanges(false);
            }}
            placeholder="What needs to change?"
            className="w-full text-sm px-3 py-2 outline-none"
            style={{
              backgroundColor: theme.colors.surfaceInput,
              borderRadius: `${theme.layout.borderRadius.input}px`,
              color: theme.colors.textPrimary,
            }}
          />
        </div>
      )}

      {/* Actions */}
      <div
        className="flex justify-end gap-2 px-5 py-3 border-t"
        style={{ borderColor: theme.colors.borderSubtle }}
      >
        <button
          onClick={handleRequestChanges}
          className="px-4 py-2 text-sm border"
          style={{
            borderColor: theme.colors.borderSubtle,
            color: theme.colors.textPrimary,
            borderRadius: `${theme.layout.borderRadius.button}px`,
            backgroundColor: theme.colors.white,
          }}
        >
          {requestingChanges ? "Send Note" : theme.gates.requestChangesText}
        </button>
        <button
          onClick={handleApprove}
          disabled={approved}
          className="px-5 py-2 text-sm font-medium"
          style={{
            backgroundColor: approved ? theme.colors.accent : theme.colors.btnPrimaryBg,
            color: theme.colors.btnPrimaryText,
            borderRadius: `${theme.layout.borderRadius.button}px`,
            transition: "background-color 200ms ease",
          }}
        >
          {approved ? "✓" : `${theme.gates.approveButtonText} →`}
        </button>
      </div>
    </div>
  );
}
