import { deriveLensOptions, useAppState } from "../../context/AppContext";
import { useTheme } from "../../context/ThemeContext";
import { disableDemoMode, enableDemoMode } from "../../lib/demoMode";
import StatusPill from "../shared/StatusPill";
import LensSelector from "../workspace/LensSelector";

// Constitution Article V: "Backend mode MUST be visible."
// Pulled from Vite-injected env; defaults to "local" when unset.
const BACKEND_MODE: "local" | "deployed" =
  ((import.meta as any).env?.VITE_BACKEND_MODE as "local" | "deployed") ?? "local";

export default function ContextBar() {
  const { state, dispatch } = useAppState();
  const { theme } = useTheme();

  const toggleDemo = () => {
    if (state.demoMode.enabled) disableDemoMode(dispatch);
    else enableDemoMode(dispatch, "user_toggle");
  };

  const stepLabels: Record<number, string> = {
    0: theme.steps.step0Label,
    1: theme.steps.step1Label,
    2: theme.steps.step2Label,
    3: theme.steps.step3Label,
    4: theme.steps.step4Label,
  };

  const currentStep = state.lifecycle.current_step;
  const status = state.lifecycle.step_statuses[currentStep];
  const memoryUnreachable = state.memoryStatus === "unreachable";

  return (
    <div
      className="flex flex-col border-b shrink-0"
      style={{ borderColor: theme.colors.borderSubtle }}
    >
      <div
        className="flex items-center justify-between px-4"
        style={{ height: `${theme.layout.contextBarHeight}px` }}
      >
        <div className="flex items-center gap-2">
          <span
            className="text-sm"
            style={{ color: theme.colors.textPrimary, fontWeight: theme.typography.mediumWeight }}
          >
            {state.sourceContext?.productName || theme.scenario.dataProductName}
          </span>
          <span className="mx-1 text-sm" style={{ color: theme.colors.textTertiary }}>
            &middot;
          </span>
          <span className="text-sm" style={{ color: theme.colors.textSecondary }}>
            Step {currentStep} &mdash; {stepLabels[currentStep]}
          </span>
          <BackendModeBadge mode={BACKEND_MODE} />
          {state.demoMode.enabled && <DemoModeBadge />}
          {/* 002-dsa-hub-pinnacle US1: lens selector renders only when ≥1 live connection. */}
          <LensSelector
            options={deriveLensOptions(state.workspaceConnections)}
            value={state.activeLens}
            onChange={(lens) => dispatch({ type: "LENS_SET", lens })}
          />
        </div>
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={toggleDemo}
            className="text-[11px] rounded px-2 py-0.5"
            style={{
              background: state.demoMode.enabled ? theme.colors.accentSurface : "transparent",
              color: state.demoMode.enabled ? theme.colors.accent : theme.colors.textSecondary,
              border: `1px solid ${theme.colors.borderSubtle}`,
            }}
            title="Switch between live backend and pre-scripted demo content"
          >
            {state.demoMode.enabled ? "Demo mode ON" : "Demo mode OFF"}
          </button>
          <StatusPill status={status} />
        </div>
      </div>
      {memoryUnreachable && (
        <div
          className="px-4 py-1.5 text-xs"
          style={{
            background: theme.colors.flagAmberSurface,
            color: theme.colors.flagAmber,
            borderTop: `1px solid ${theme.colors.borderSubtle}`,
          }}
        >
          Conversation memory is unavailable — refresh durability is lost for this session.
        </div>
      )}
    </div>
  );
}

function BackendModeBadge({ mode }: { mode: "local" | "deployed" }) {
  const bg = mode === "deployed" ? "#2563EB" : "#475569";
  return (
    <span
      className="text-[10px] uppercase tracking-wide rounded px-1.5 py-0.5"
      style={{ background: bg, color: "#F1F5F9" }}
      title={`Backend mode: ${mode}`}
    >
      {mode}
    </span>
  );
}

// Inline header badge — the bigger corner badge in the artifact panel lives
// in components/shared/DemoBadge.tsx (T061).
function DemoModeBadge() {
  return (
    <span
      className="text-[10px] uppercase tracking-wide rounded px-1.5 py-0.5"
      style={{ background: "#F97316", color: "#0F172A", fontWeight: 700 }}
      title="Demo mode — content is pre-scripted"
    >
      demo
    </span>
  );
}
