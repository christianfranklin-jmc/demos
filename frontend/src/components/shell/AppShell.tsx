import { useState } from "react";
import { useTheme } from "../../context/ThemeContext";
import { useWorkspaceContextSync } from "../../hooks/useWorkspaceContextSync";
import { getOrMintSessionId } from "../../lib/session";
import Sidebar from "./Sidebar";
import ContextBar from "./ContextBar";
import ChatPanel from "../chat/ChatPanel";
import ArtifactPanel from "../artifact/ArtifactPanel";
import Connections from "../../routes/Connections";
import Step1Discovery from "../../routes/Step1Discovery";
import Build from "../../routes/Build";
import Semantic from "../../routes/Semantic";
import RedundancyGate from "../gates/RedundancyGate";
import {
  useRedundancyCheck,
  type RedundancyReport,
} from "../../hooks/useRedundancyCheck";

interface AppShellProps {
  onSettingsOpen: () => void;
}

// 002-dsa-hub-pinnacle US1..US5: view-mode toggle so the Connections,
// Discovery, Build, and Semantic pages coexist with the existing 4-step
// workflow without a router.
export type ShellView =
  | "workflow"
  | "connections"
  | "discovery"
  | "build"
  | "semantic";

const BACKEND_URL: string =
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  (import.meta as any).env?.VITE_BACKEND_URL ?? "http://localhost:8080";

export default function AppShell({ onSettingsOpen }: AppShellProps) {
  const { theme } = useTheme();
  const [view, setView] = useState<ShellView>("workflow");
  const [activeRunId, setActiveRunId] = useState<string | null>(null);
  const [provisionError, setProvisionError] = useState<string | null>(null);

  // 002-dsa-hub-pinnacle US6 — redundancy gate state.
  const [pendingPrd, setPendingPrd] = useState<unknown | null>(null);
  const [redundancyReport, setRedundancyReport] =
    useState<RedundancyReport | null>(null);

  // Mirror /workspace/* into AppContext so Sidebar + ContextBar see the
  // live state regardless of which view is currently mounted.
  useWorkspaceContextSync();

  const { check: runRedundancyCheck, decide: recordDecisions } =
    useRedundancyCheck();

  // 002-dsa-hub-pinnacle US3 + US6 — pill click → run redundancy gate
  // → if cleared → POST /workflow/provision → navigate to Build.
  async function startProvisioning(prdJson: unknown): Promise<void> {
    setProvisionError(null);
    setPendingPrd(prdJson);
    try {
      const report = await runRedundancyCheck(prdJson);
      setRedundancyReport(report);
      // Auto-skip the modal when net_new (gate already cleared).
      if (report.state === "net_new" && report.cleared_to_provision) {
        setRedundancyReport(null);
        await provisionWith(prdJson, report.report_id);
      }
    } catch (exc) {
      setProvisionError(exc instanceof Error ? exc.message : String(exc));
      setPendingPrd(null);
    }
  }

  async function provisionWith(
    prd: unknown,
    redundancy_report_id: string
  ): Promise<void> {
    const r = await fetch(`${BACKEND_URL}/workflow/provision`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-DSA-Session-ID": getOrMintSessionId(),
      },
      body: JSON.stringify({
        prd,
        redundancy_report_id,
        redundancy_cleared: true,
      }),
    });
    if (r.status !== 201) {
      let msg = `provision failed (HTTP ${r.status})`;
      try {
        const body = await r.json();
        if (body?.detail?.message) msg = body.detail.message;
      } catch {
        // ignore
      }
      setProvisionError(msg);
      return;
    }
    const run = await r.json();
    setActiveRunId(run.run_id);
    setView("build");
    setPendingPrd(null);
    setRedundancyReport(null);
  }

  return (
    <div className="flex h-screen w-screen overflow-hidden" style={{ backgroundColor: theme.colors.white }}>
      <Sidebar
        onSettingsOpen={onSettingsOpen}
        view={view}
        onViewChange={setView}
      />

      <main className="flex-1 flex flex-col min-w-0">
        <ContextBar />

        {view === "workflow" ? (
          /* Split Panel Area — single-source workflow (preserved) */
          <div className="flex-1 flex min-h-0">
            <ChatPanel />
            <ArtifactPanel />
          </div>
        ) : view === "discovery" ? (
          /* Multi-source business-process discovery (US2) */
          <div className="flex-1 min-h-0 overflow-y-auto">
            {provisionError ? (
              <div
                role="alert"
                className="text-xs px-3 py-2 mx-6 mt-6 rounded"
                style={{ color: "#DC2626", backgroundColor: "#DC262614" }}
              >
                {provisionError}
              </div>
            ) : null}
            <Step1Discovery
              onPillAccepted={(_pill, prd) => {
                // 002-dsa-hub-pinnacle US3 (T088): the click path is now
                // wired — POST /workflow/provision then navigate to Build.
                void startProvisioning(prd);
              }}
            />
          </div>
        ) : view === "build" ? (
          /* Provisioning DAG control room (US3) */
          <div className="flex-1 min-h-0 overflow-y-auto">
            <Build run_id={activeRunId} onBack={() => setView("discovery")} />
          </div>
        ) : view === "semantic" ? (
          /* Per-connection semantic graph (US5) */
          <div className="flex-1 min-h-0 overflow-y-auto">
            <Semantic />
          </div>
        ) : (
          /* Multi-source workspace (US1) */
          <div className="flex-1 min-h-0 overflow-y-auto">
            <Connections />
          </div>
        )}
      </main>

      {/* US6 — redundancy gate modal between PRD draft and provisioning. */}
      {redundancyReport && pendingPrd ? (
        <RedundancyGate
          report={redundancyReport}
          onCancel={() => {
            setRedundancyReport(null);
            setPendingPrd(null);
          }}
          onDecide={async (decisions, override_rationale) => {
            const res = await recordDecisions(
              redundancyReport.report_id,
              decisions,
              override_rationale
            );
            // Reflect updated cleared state back into the visible report so
            // the modal can show "still pending" if any are missing.
            if (!res.cleared_to_provision) {
              setRedundancyReport((prev) =>
                prev
                  ? {
                      ...prev,
                      cleared_to_provision: false,
                    }
                  : prev
              );
            }
            return {
              cleared_to_provision: res.cleared_to_provision,
              pending_overlaps: res.pending_overlaps,
            };
          }}
          onCleared={() => {
            void provisionWith(pendingPrd, redundancyReport.report_id);
          }}
        />
      ) : null}
    </div>
  );
}
