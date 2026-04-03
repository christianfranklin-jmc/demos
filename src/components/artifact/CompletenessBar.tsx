import { useTheme } from "../../context/ThemeContext";

interface CompletenessBarProps {
  score: number;
}

export default function CompletenessBar({ score }: CompletenessBarProps) {
  const { theme } = useTheme();

  if (!theme.features.showCompletenessBar) return null;

  const clamped = Math.max(0, Math.min(100, Math.round(score)));

  return (
    <div className="flex items-center gap-3 px-4 py-3">
      <div
        className="flex-1 h-1.5 rounded-full overflow-hidden"
        style={{ backgroundColor: theme.colors.surfaceInput }}
      >
        <div
          className="h-full rounded-full"
          style={{
            width: `${clamped}%`,
            backgroundColor: theme.colors.accent,
            transition: "width 300ms ease",
          }}
        />
      </div>
      <span
        className="text-xs shrink-0"
        style={{ color: theme.colors.textSecondary }}
      >
        {clamped}%
      </span>
    </div>
  );
}
