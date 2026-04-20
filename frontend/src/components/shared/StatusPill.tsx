import { useTheme } from "../../context/ThemeContext";
import type { StepStatus } from "../../lib/types";

interface StatusPillProps {
  status: StepStatus;
}

const STATUS_LABELS: Record<StepStatus, string> = {
  not_started: "Not Started",
  in_progress: "In Progress",
  awaiting_approval: "Awaiting Approval",
  approved: "Complete",
  skipped: "Skipped",
};

export default function StatusPill({ status }: StatusPillProps) {
  const { theme } = useTheme();

  const colorMap: Record<StepStatus, string> = {
    in_progress: theme.colors.accent,
    awaiting_approval: theme.colors.flagAmber,
    approved: theme.colors.textTertiary,
    not_started: theme.colors.borderSubtle,
    skipped: theme.colors.textTertiary,
  };

  return (
    <span
      className="inline-flex items-center gap-1.5 text-xs"
      style={{ color: theme.colors.textSecondary }}
    >
      <span
        className="w-2 h-2 rounded-full"
        style={{ backgroundColor: colorMap[status] }}
      />
      {STATUS_LABELS[status]}
    </span>
  );
}
