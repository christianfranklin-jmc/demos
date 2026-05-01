// RedundancyGate — modal between PRD draft and acceptance (T121, US6).
//
// Shows the report state + per-overlap reuse-or-override cards. The
// AppShell consumes the resulting "cleared" outcome and proceeds to
// POST /workflow/provision with the report_id when cleared.

import { useEffect, useMemo, useState } from "react";
import { useTheme } from "../../context/ThemeContext";
import type {
  OverlapItem,
  RedundancyReport,
} from "../../hooks/useRedundancyCheck";

interface Props {
  report: RedundancyReport;
  onCancel: () => void;
  onDecide: (
    decisions: {
      overlap_existing_id: string;
      kind: "reuse" | "override";
      rationale: string;
    }[],
    override_rationale: string | null
  ) => Promise<{ cleared_to_provision: boolean; pending_overlaps: number } | null>;
  onCleared: () => void;
}

const STATE_BANNER: Record<RedundancyReport["state"], string> = {
  net_new: "🟢 Net new — no overlaps found.",
  partial_overlap: "🟡 Partial overlap — review per-overlap decisions below.",
  duplicate: "🔴 Duplicate — full override rationale required.",
};

export default function RedundancyGate({
  report,
  onCancel,
  onDecide,
  onCleared,
}: Props) {
  const { theme } = useTheme();
  const [decisions, setDecisions] = useState<
    Record<string, { kind: "reuse" | "override"; rationale: string }>
  >({});
  const [overrideRationale, setOverrideRationale] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Auto-clear on net_new (the report already came back cleared_to_provision=true).
  useEffect(() => {
    if (report.state === "net_new" && report.cleared_to_provision) {
      onCleared();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [report.report_id]);

  const blocking = useMemo(() => {
    if (report.state === "net_new") return false;
    const hasAll = report.overlaps.every((o) => decisions[o.existing_id]);
    if (!hasAll) return true;
    if (report.state === "duplicate" && !overrideRationale.trim()) return true;
    return false;
  }, [decisions, overrideRationale, report.overlaps, report.state]);

  async function submit() {
    setSubmitting(true);
    setError(null);
    try {
      const payload = report.overlaps
        .map((o) => {
          const d = decisions[o.existing_id];
          if (!d) return null;
          return {
            overlap_existing_id: o.existing_id,
            kind: d.kind,
            rationale: d.rationale,
          };
        })
        .filter(
          (
            x
          ): x is {
            overlap_existing_id: string;
            kind: "reuse" | "override";
            rationale: string;
          } => x !== null
        );
      const res = await onDecide(
        payload,
        overrideRationale.trim() || null
      );
      if (res?.cleared_to_provision) {
        onCleared();
      } else {
        setError(
          `not yet cleared — ${res?.pending_overlaps ?? "?"} overlap(s) still pending`
        );
      }
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Redundancy check"
      data-testid="redundancy-gate"
      className="fixed inset-0 z-50 flex items-center justify-center"
      style={{ backgroundColor: "rgba(0,0,0,0.55)" }}
    >
      <div
        className="w-[640px] max-h-[85vh] overflow-y-auto rounded-lg p-6 flex flex-col gap-4"
        style={{
          backgroundColor: theme.colors.surfaceSubtle,
          border: `1px solid ${theme.colors.borderSubtle}`,
        }}
      >
        <h2
          className="text-lg font-semibold"
          style={{ color: theme.colors.textPrimary }}
        >
          Redundancy check
        </h2>
        <div
          className="text-sm px-3 py-2 rounded"
          style={{
            backgroundColor: theme.colors.white,
            color: theme.colors.textPrimary,
            border: `1px solid ${theme.colors.borderSubtle}`,
          }}
        >
          {STATE_BANNER[report.state]}
        </div>

        {report.overlaps.length > 0 ? (
          <div className="flex flex-col gap-3">
            {report.overlaps.map((o) => (
              <OverlapCard
                key={o.existing_id}
                overlap={o}
                decision={decisions[o.existing_id]}
                onChange={(kind, rationale) =>
                  setDecisions((prev) => ({
                    ...prev,
                    [o.existing_id]: { kind, rationale },
                  }))
                }
              />
            ))}
          </div>
        ) : null}

        {report.state === "duplicate" ? (
          <label
            className="flex flex-col gap-1 text-xs"
            style={{ color: theme.colors.textSecondary }}
          >
            Override rationale
            <textarea
              data-testid="override-rationale"
              value={overrideRationale}
              onChange={(e) => setOverrideRationale(e.target.value)}
              rows={3}
              placeholder="Why ship this duplicate? (e.g., regulatory schema rewrite)"
              className="w-full px-2 py-1.5 rounded font-sans text-sm"
              style={{
                backgroundColor: theme.colors.white,
                color: theme.colors.textPrimary,
                border: `1px solid ${theme.colors.borderSubtle}`,
              }}
            />
          </label>
        ) : null}

        {error ? (
          <div
            role="alert"
            className="text-xs px-3 py-2 rounded"
            style={{ color: "#DC2626", backgroundColor: "#DC262614" }}
          >
            {error}
          </div>
        ) : null}

        <div className="flex items-center justify-end gap-2">
          <button
            type="button"
            onClick={onCancel}
            className="px-3 py-1.5 rounded"
            style={{
              color: theme.colors.textSecondary,
              border: `1px solid ${theme.colors.borderSubtle}`,
            }}
          >
            Cancel
          </button>
          {report.state === "net_new" ? (
            <button
              type="button"
              onClick={onCleared}
              className="px-3 py-1.5 rounded font-semibold"
              style={{
                color: theme.colors.white,
                backgroundColor: theme.colors.accent,
              }}
            >
              Continue
            </button>
          ) : (
            <button
              type="button"
              onClick={submit}
              disabled={blocking || submitting}
              className="px-3 py-1.5 rounded font-semibold"
              style={{
                color: theme.colors.white,
                backgroundColor: theme.colors.accent,
                opacity: blocking || submitting ? 0.5 : 1,
              }}
            >
              {submitting ? "Submitting…" : "Accept & continue"}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

interface OverlapCardProps {
  overlap: OverlapItem;
  decision: { kind: "reuse" | "override"; rationale: string } | undefined;
  onChange: (kind: "reuse" | "override", rationale: string) => void;
}

function OverlapCard({ overlap, decision, onChange }: OverlapCardProps) {
  const { theme } = useTheme();
  return (
    <div
      data-testid="overlap-card"
      data-existing-id={overlap.existing_id}
      className="rounded-md p-3 flex flex-col gap-2"
      style={{
        backgroundColor: theme.colors.white,
        border: `1px solid ${theme.colors.borderSubtle}`,
      }}
    >
      <div className="flex items-baseline justify-between gap-2">
        <div
          className="text-sm font-semibold"
          style={{ color: theme.colors.textPrimary }}
        >
          {overlap.kind} · {overlap.proposed_name}
        </div>
        <div
          className="text-xs tabular-nums"
          style={{ color: theme.colors.textTertiary }}
        >
          {overlap.overlap_pct.toFixed(0)}% match
        </div>
      </div>
      <pre
        className="text-[11px] whitespace-pre-wrap font-mono px-2 py-1 rounded"
        style={{
          backgroundColor: theme.colors.surfaceSubtle,
          color: theme.colors.textSecondary,
        }}
      >
        {overlap.side_by_side_diff}
      </pre>
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={() => onChange("reuse", decision?.rationale ?? "")}
          className="px-2 py-1 rounded text-xs"
          style={{
            color:
              decision?.kind === "reuse"
                ? theme.colors.white
                : theme.colors.textSecondary,
            backgroundColor:
              decision?.kind === "reuse" ? theme.colors.accent : "transparent",
            border: `1px solid ${theme.colors.borderSubtle}`,
          }}
        >
          Reuse existing
        </button>
        <button
          type="button"
          onClick={() => onChange("override", decision?.rationale ?? "")}
          className="px-2 py-1 rounded text-xs"
          style={{
            color:
              decision?.kind === "override"
                ? theme.colors.white
                : theme.colors.textSecondary,
            backgroundColor:
              decision?.kind === "override"
                ? "var(--status-error, #DC2626)"
                : "transparent",
            border: `1px solid ${theme.colors.borderSubtle}`,
          }}
        >
          Override
        </button>
        {decision?.kind === "override" ? (
          <input
            type="text"
            value={decision.rationale}
            placeholder="rationale"
            onChange={(e) => onChange("override", e.target.value)}
            className="flex-1 px-2 py-1 rounded text-xs"
            style={{
              backgroundColor: theme.colors.surfaceSubtle,
              color: theme.colors.textPrimary,
              border: `1px solid ${theme.colors.borderSubtle}`,
            }}
          />
        ) : null}
      </div>
    </div>
  );
}
