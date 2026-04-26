// LensSelector — workspace lens dropdown (T046, US1).
//
// Renders the active lens (`All sources` or a specific connection scope) and
// the dropdown of available options. The "All sources" option is only
// included once ≥2 live connections exist (FR-005); below that, the
// selector is hidden entirely.

import { useTheme } from "../../context/ThemeContext";
import type { LensOption, WorkspaceLens } from "../../context/AppContext";

interface Props {
  options: LensOption[];
  value: WorkspaceLens;
  onChange: (lens: WorkspaceLens) => void;
}

export default function LensSelector({ options, value, onChange }: Props) {
  const { theme } = useTheme();
  if (options.length === 0) return null;

  const currentKey = value.kind === "all" ? "all" : `connection:${value.connection_id}`;

  return (
    <select
      data-testid="lens-selector"
      value={currentKey}
      onChange={(e) => {
        const key = e.target.value;
        if (key === "all") {
          onChange({ kind: "all" });
        } else if (key.startsWith("connection:")) {
          onChange({
            kind: "connection",
            connection_id: key.slice("connection:".length),
          });
        }
      }}
      className="text-[11px] rounded px-2 py-0.5"
      style={{
        background: "transparent",
        color: theme.colors.textSecondary,
        border: `1px solid ${theme.colors.borderSubtle}`,
      }}
      title="Switch the active workspace lens"
    >
      {options.map((opt) => {
        const key =
          opt.kind === "all" ? "all" : `connection:${opt.connection_id ?? ""}`;
        return (
          <option key={key} value={key}>
            {opt.label}
          </option>
        );
      })}
    </select>
  );
}
