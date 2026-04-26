// Build — provisioning DAG control room (T082, US3 / US-3 acceptance scenarios).
//
// Live view of a ProvisioningRun: KPI strip, agent DAG, activity stream,
// validation card, and a terminal banner showing product final/provisional
// state. Driven entirely by the v2 SSE event stream via useProvisioningRun.

import { useMemo } from "react";
import { useTheme } from "../context/ThemeContext";
import {
  AGENT_ORDER,
  emptyRunState,
  useProvisioningRun,
} from "../hooks/useProvisioningRun";
import AgentDAG from "../components/build/AgentDAG";
import ActivityStream from "../components/build/ActivityStream";
import BuildKPIStrip from "../components/build/BuildKPIStrip";

interface Props {
  run_id: string | null;
  onBack?: () => void;
}

export default function Build({ run_id, onBack }: Props) {
  const { snapshot, retry } = useProvisioningRun(run_id);
  const { theme } = useTheme();

  const allCompleted = useMemo(
    () => snapshot.agents.every((a) => a.state === "completed"),
    [snapshot.agents]
  );

  if (!run_id) {
    return (
      <div className="flex flex-col gap-3 p-6">
        <h1
          className="text-2xl font-semibold"
          style={{ color: theme.colors.textPrimary }}
        >
          Build
        </h1>
        <div
          className="rounded-lg p-6 text-sm"
          style={{
            color: theme.colors.textSecondary,
            backgroundColor: theme.colors.surfaceSubtle,
            border: `1px dashed ${theme.colors.borderSubtle}`,
          }}
          data-testid="build-empty"
        >
          No active run. Click a pill on the Discovery page to start a
          provisioning run.
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6 p-6">
      <header className="flex items-start justify-between gap-4">
        <div>
          <h1
            className="text-2xl font-semibold"
            style={{ color: theme.colors.textPrimary }}
          >
            Build
          </h1>
          <p
            className="text-sm mt-1"
            style={{ color: theme.colors.textSecondary }}
            title={run_id}
          >
            run <code className="font-mono text-xs">{run_id.slice(0, 12)}…</code>{" "}
            · state{" "}
            <strong style={{ color: theme.colors.textPrimary }}>
              {snapshot.state}
            </strong>
          </p>
        </div>
        {onBack ? (
          <button
            type="button"
            onClick={onBack}
            className="px-3 py-2 rounded text-sm shrink-0"
            style={{
              color: theme.colors.textSecondary,
              border: `1px solid ${theme.colors.borderSubtle}`,
            }}
          >
            ← Back
          </button>
        ) : null}
      </header>

      {/* Terminal banner (final / provisional / failed) */}
      {snapshot.state === "completed" || snapshot.state === "needs_replan" ? (
        <TerminalBanner snapshot={snapshot} />
      ) : null}

      {/* Stream error */}
      {snapshot.state === "stream_error" ? (
        <div
          role="alert"
          className="text-xs px-3 py-2 rounded"
          style={{ color: "#DC2626", backgroundColor: "#DC262614" }}
        >
          stream error: {snapshot.error}
        </div>
      ) : null}

      <BuildKPIStrip ticks={snapshot.ticks} />

      {/* Agent DAG */}
      <section className="flex flex-col gap-2">
        <h2
          className="text-base font-semibold"
          style={{ color: theme.colors.textPrimary }}
        >
          Agents{" "}
          <span
            className="text-sm font-normal"
            style={{ color: theme.colors.textTertiary }}
          >
            ({snapshot.agents.filter((a) => a.state === "completed").length}/
            {AGENT_ORDER.length} complete)
          </span>
        </h2>
        <AgentDAG agents={snapshot.agents} onRetry={retry} />
      </section>

      {/* Activity stream + validation card side by side */}
      <section className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="flex flex-col gap-2 min-h-0">
          <h2
            className="text-base font-semibold"
            style={{ color: theme.colors.textPrimary }}
          >
            Activity
          </h2>
          <ActivityStream rows={snapshot.activity} />
        </div>
        <div className="flex flex-col gap-2 min-h-0">
          <h2
            className="text-base font-semibold"
            style={{ color: theme.colors.textPrimary }}
          >
            Validation{" "}
            <span
              className="text-sm font-normal"
              style={{ color: theme.colors.textTertiary }}
            >
              ({snapshot.validation_results.filter((r) => r.state === "passed").length}/
              {snapshot.validation_results.length} passing)
            </span>
          </h2>
          <ValidationCard rows={snapshot.validation_results} />
        </div>
      </section>

      {/* Hidden state-only flag so the test harness can assert "all complete". */}
      <span
        data-testid="build-all-complete"
        data-value={allCompleted ? "true" : "false"}
        hidden
      />
    </div>
  );
}

function TerminalBanner({
  snapshot,
}: {
  snapshot: ReturnType<typeof emptyRunState>;
}) {
  const { theme } = useTheme();
  const passRate = snapshot.validation_pass_rate ?? 0;
  const isFinal = snapshot.product_state === "final";
  const color = isFinal ? "#16A34A" : "#F97316";
  return (
    <div
      role="status"
      className="rounded-lg p-3 flex items-center justify-between gap-3"
      style={{
        backgroundColor: `${color}14`,
        border: `1px solid ${color}55`,
        color: theme.colors.textPrimary,
      }}
    >
      <div className="flex items-center gap-2">
        <span aria-hidden>{isFinal ? "✓" : "!"}</span>
        <span className="font-semibold">
          {isFinal ? "Product registered as final" : "Product registered as provisional"}
        </span>
        <span
          className="text-xs"
          style={{ color: theme.colors.textTertiary }}
        >
          · validation pass rate {(passRate * 100).toFixed(0)}%
        </span>
      </div>
      {snapshot.product_id ? (
        <code
          className="font-mono text-xs"
          style={{ color: theme.colors.textTertiary }}
        >
          {snapshot.product_id.slice(0, 12)}…
        </code>
      ) : null}
    </div>
  );
}

function ValidationCard({
  rows,
}: {
  rows: ReturnType<typeof emptyRunState>["validation_results"];
}) {
  const { theme } = useTheme();
  if (!rows.length) {
    return (
      <div
        data-testid="validation-empty"
        className="rounded-lg p-3 text-xs"
        style={{
          color: theme.colors.textTertiary,
          backgroundColor: theme.colors.surfaceSubtle,
          border: `1px solid ${theme.colors.borderSubtle}`,
        }}
      >
        No validation results yet — they appear when delivery_agent runs.
      </div>
    );
  }
  return (
    <div
      className="rounded-lg overflow-y-auto max-h-[420px]"
      style={{
        backgroundColor: theme.colors.surfaceSubtle,
        border: `1px solid ${theme.colors.borderSubtle}`,
      }}
    >
      {rows.map((row, i) => (
        <details
          key={i}
          className="px-3 py-2"
          style={{
            borderTop:
              i === 0 ? "none" : `1px solid ${theme.colors.borderSubtle}`,
          }}
        >
          <summary
            className="cursor-pointer flex items-center gap-2 text-sm"
            style={{ color: theme.colors.textPrimary }}
          >
            <span
              aria-hidden
              style={{
                color: row.state === "passed" ? "#16A34A" : "#DC2626",
              }}
            >
              {row.state === "passed" ? "✓" : "✗"}
            </span>
            <span className="break-words">{row.question}</span>
          </summary>
          <div
            className="mt-2 text-xs flex flex-col gap-1"
            style={{ color: theme.colors.textSecondary }}
          >
            {row.sql_executed ? (
              <code
                className="font-mono text-[11px] block px-2 py-1 rounded"
                style={{
                  backgroundColor: theme.colors.surfaceInput,
                  color: theme.colors.textPrimary,
                }}
              >
                {row.sql_executed}
              </code>
            ) : null}
            <span>
              latency {row.latency_ms ?? "—"}ms · {row.judge_reasoning}
            </span>
          </div>
        </details>
      ))}
    </div>
  );
}
