import { useAppState } from "../../context/AppContext";
import { useTheme } from "../../context/ThemeContext";
import StatusPill from "../shared/StatusPill";

export default function ContextBar() {
  const { state } = useAppState();
  const { theme } = useTheme();

  const stepLabels: Record<number, string> = {
    0: theme.steps.step0Label,
    1: theme.steps.step1Label,
    2: theme.steps.step2Label,
    3: theme.steps.step3Label,
    4: theme.steps.step4Label,
  };

  const currentStep = state.lifecycle.current_step;
  const status = state.lifecycle.step_statuses[currentStep];

  return (
    <div
      className="flex items-center justify-between px-4 border-b shrink-0"
      style={{
        height: `${theme.layout.contextBarHeight}px`,
        borderColor: theme.colors.borderSubtle,
      }}
    >
      <div className="flex items-center">
        <span
          className="text-sm"
          style={{ color: theme.colors.textPrimary, fontWeight: theme.typography.mediumWeight }}
        >
          {theme.scenario.dataProductName}
        </span>
        <span className="mx-2 text-sm" style={{ color: theme.colors.textTertiary }}>
          &middot;
        </span>
        <span className="text-sm" style={{ color: theme.colors.textSecondary }}>
          Step {currentStep} &mdash; {stepLabels[currentStep]}
        </span>
      </div>
      <StatusPill status={status} />
    </div>
  );
}
