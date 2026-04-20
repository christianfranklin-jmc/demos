// Confirmation modal for FR-010: re-running an earlier step that has approved
// downstream gates invalidates those gates and their artifacts. The user MUST
// explicitly accept before the cascade runs (Constitution Article VI —
// "Human gates are deliberate moments").

import type { StepNumber } from "../../lib/types";

const STEP_LABELS: Record<StepNumber, string> = {
  0: "Stakeholders",
  1: "Requirements",
  2: "Conceptual Model",
  3: "Logical Model",
  4: "Detailed Requirements",
};

interface Props {
  isOpen: boolean;
  fromStep: StepNumber;
  invalidatedSteps: StepNumber[];
  onConfirm: () => void;
  onCancel: () => void;
}

export function InvalidationConfirm({
  isOpen,
  fromStep,
  invalidatedSteps,
  onConfirm,
  onCancel,
}: Props): JSX.Element | null {
  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60"
      role="dialog"
      aria-modal="true"
      aria-labelledby="invalidation-title"
    >
      <div className="max-w-md rounded-md border border-slate-700 bg-slate-900 p-6 text-slate-100 shadow-xl">
        <h2 id="invalidation-title" className="mb-2 text-lg font-semibold">
          Re-running Step {fromStep} ({STEP_LABELS[fromStep]})
        </h2>
        <p className="mb-4 text-sm text-slate-300">
          The following approved step{invalidatedSteps.length > 1 ? "s" : ""} and their artifacts
          will be <span className="font-semibold text-orange-400">invalidated</span> and must be
          re-run:
        </p>
        <ul className="mb-6 list-inside list-disc text-sm text-slate-200">
          {invalidatedSteps.map((s) => (
            <li key={s}>
              Step {s} — {STEP_LABELS[s]}
            </li>
          ))}
        </ul>
        <div className="flex justify-end gap-2">
          <button
            type="button"
            onClick={onCancel}
            className="rounded border border-slate-600 px-4 py-2 text-sm text-slate-200 hover:bg-slate-800"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={onConfirm}
            className="rounded bg-orange-600 px-4 py-2 text-sm font-semibold text-white hover:bg-orange-700"
          >
            Invalidate and re-run
          </button>
        </div>
      </div>
    </div>
  );
}
