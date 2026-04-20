// T061: Demo-mode indicator badge (FR-018).
//
// Rendered on every artifact panel while AppContext.demoMode.enabled is true.
// Per Constitution Article V, uses phData orange (#F97316) on a dark surface
// so the user cannot mistake demo content for live customer data.

import { useAppState } from "../../context/AppContext";

interface Props {
  corner?: "top-right" | "top-left" | "bottom-right" | "bottom-left";
}

const POSITION: Record<NonNullable<Props["corner"]>, string> = {
  "top-right": "top-2 right-2",
  "top-left": "top-2 left-2",
  "bottom-right": "bottom-2 right-2",
  "bottom-left": "bottom-2 left-2",
};

export default function DemoBadge({ corner = "top-right" }: Props): JSX.Element | null {
  const { state } = useAppState();
  if (!state.demoMode.enabled) return null;

  return (
    <span
      className={`absolute ${POSITION[corner]} z-10 text-[10px] uppercase tracking-wider rounded px-2 py-0.5 pointer-events-none select-none`}
      style={{
        background: "#F97316",
        color: "#0F172A",
        fontWeight: 700,
        boxShadow: "0 1px 3px rgba(0,0,0,0.4)",
      }}
      title={
        state.demoMode.reason === "auto_fallback"
          ? "Auto-fallback: backend call failed, showing pre-scripted content"
          : "Demo mode: content is pre-scripted (not live customer data)"
      }
    >
      DEMO
    </span>
  );
}
