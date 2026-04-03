import { useTheme } from "../../context/ThemeContext";
import { FLAG_CONFIG } from "../../lib/constants";
import type { FlagType, FlagStatus } from "../../lib/types";

interface FlagBadgeProps {
  type: FlagType;
  status?: FlagStatus;
}

export default function FlagBadge({ type, status = "open" }: FlagBadgeProps) {
  const { theme } = useTheme();
  const config = FLAG_CONFIG[type];
  if (!config) return null;

  const isResolved = status === "resolved" || status === "deferred";

  return (
    <span
      className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-xs font-medium"
      style={{
        backgroundColor: isResolved
          ? theme.colors.surfaceInput
          : config.color + "20",
        color: isResolved ? theme.colors.textTertiary : config.color,
        textDecoration: isResolved ? "line-through" : "none",
      }}
    >
      {isResolved ? "✓" : "!"} {config.label}
    </span>
  );
}
