import { useAppState } from "../../context/AppContext";
import { useTheme } from "../../context/ThemeContext";
import { getStandardsByCategory } from "../../data/standards";
import { validateStandards } from "../../lib/validation";
import type { StepNumber } from "../../lib/types";

interface StandardsViewProps {
  stepNumber: StepNumber;
}

const SEVERITY_CONFIG: Record<string, { label: string; colorKey: string }> = {
  error: { label: "Required", colorKey: "flagRed" },
  warning: { label: "Recommended", colorKey: "flagAmber" },
  info: { label: "Best Practice", colorKey: "flagBlue" },
};

export default function StandardsView({ stepNumber }: StandardsViewProps) {
  const { state } = useAppState();
  const { theme } = useTheme();
  const grouped = getStandardsByCategory(stepNumber);

  // Get the current artifact for pass/fail checking
  const artifact = stepNumber === 1 ? state.artifacts.prd
    : stepNumber === 2 ? state.artifacts.conceptual
    : stepNumber === 3 ? state.artifacts.logical
    : state.artifacts.detailed;

  const results = validateStandards(stepNumber, artifact);
  const resultMap = new Map(results.map((r) => [r.standard.id, r.passes]));

  const categories = Object.keys(grouped);

  if (categories.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center px-8">
        <p className="text-sm italic text-center" style={{ color: theme.colors.textTertiary }}>
          No standards defined for this step yet.
        </p>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto px-4 py-4">
      <div className="mb-4">
        <h2 className="text-sm font-medium" style={{ color: theme.colors.textPrimary }}>
          Quality Standards
        </h2>
        <p className="text-xs mt-1" style={{ color: theme.colors.textTertiary }}>
          These guidelines define what a well-formed artifact looks like at this step.
        </p>
      </div>

      {categories.map((category) => (
        <div key={category} className="mb-5">
          <h3
            className="text-xs font-semibold uppercase tracking-wider mb-2"
            style={{ color: theme.colors.textSecondary }}
          >
            {category}
          </h3>
          <div className="flex flex-col gap-2">
            {grouped[category].map((standard) => {
              const passes = resultMap.get(standard.id);
              const hasArtifact = artifact !== null;
              const sevConfig = SEVERITY_CONFIG[standard.severity];
              const sevColor = (theme.colors as any)[sevConfig.colorKey] || theme.colors.textTertiary;

              return (
                <div
                  key={standard.id}
                  className="px-3 py-3 rounded-lg border"
                  style={{
                    borderColor: theme.colors.borderSubtle,
                    backgroundColor: hasArtifact && passes === false
                      ? (theme.colors.flagPurpleSurface || "#EDE9FE") + "40"
                      : theme.colors.white,
                  }}
                >
                  <div className="flex items-center gap-2 mb-1">
                    {/* Pass/fail indicator */}
                    {hasArtifact && standard.validate && (
                      <span
                        className="w-4 h-4 rounded-full flex items-center justify-center text-xs"
                        style={{
                          backgroundColor: passes
                            ? theme.colors.accent + "20"
                            : (theme.colors.flagPurple || "#8B5CF6") + "20",
                          color: passes
                            ? theme.colors.accent
                            : theme.colors.flagPurple || "#8B5CF6",
                        }}
                      >
                        {passes ? "✓" : "!"}
                      </span>
                    )}

                    {/* Severity badge */}
                    <span
                      className="text-xs px-1.5 py-0.5 rounded font-medium"
                      style={{
                        backgroundColor: sevColor + "20",
                        color: sevColor,
                        fontSize: "10px",
                      }}
                    >
                      {sevConfig.label}
                    </span>
                  </div>

                  <p className="text-sm font-medium" style={{ color: theme.colors.textPrimary }}>
                    {standard.rule}
                  </p>
                  <p className="text-xs mt-1 leading-relaxed" style={{ color: theme.colors.textTertiary }}>
                    {standard.description}
                  </p>
                </div>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}
