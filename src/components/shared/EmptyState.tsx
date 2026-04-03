import { useTheme } from "../../context/ThemeContext";
import type { StepNumber } from "../../lib/types";

interface EmptyStateProps {
  stepNumber: StepNumber;
  tabName: string;
}

const MESSAGES: Record<string, string> = {
  "1:PRD Draft":
    "Your PRD will build here as we talk. I'll ask you the key questions \u2014 nothing to fill in.",
  "2:Conceptual Model":
    "Entity cards appear here once we've confirmed your business requirements.",
  "3:Logical Model":
    "The logical model expands here after the conceptual model is approved.",
  "4:Detailed Requirements":
    "Field-level mapping appears here as we work through the logical model.",
  "0:Stakeholder Map":
    "The stakeholder map will populate as we identify key personas and their data needs.",
  Flags:
    "No flags yet \u2014 I'll surface mapping gaps or grain ambiguities here as we go.",
};

function getEmptyMessage(stepNumber: StepNumber, tabName: string): string {
  if (tabName === "Flags") return MESSAGES.Flags;
  return (
    MESSAGES[`${stepNumber}:${tabName}`] ??
    `This tab will populate as the ${tabName.toLowerCase()} takes shape.`
  );
}

export default function EmptyState({ stepNumber, tabName }: EmptyStateProps) {
  const { theme } = useTheme();

  return (
    <div className="flex-1 flex items-center justify-center px-8">
      <p
        className="text-sm italic text-center leading-relaxed"
        style={{
          color: theme.colors.textTertiary,
          maxWidth: "400px",
        }}
      >
        {getEmptyMessage(stepNumber, tabName)}
      </p>
    </div>
  );
}
