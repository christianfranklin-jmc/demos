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

interface AppShellProps {
  onSettingsOpen: () => void;
}

// 002-dsa-hub-pinnacle US1+US2+US3: view-mode toggle so the new Connections,
// Discovery, and Build pages coexist with the existing 4-step workflow
// without a router.
export type ShellView = "workflow" | "connections" | "discovery" | "build";

const BACKEND_URL: string =
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  (import.meta as any).env?.VITE_BACKEND_URL ?? "http://localhost:8080";

export default function AppShell({ onSettingsOpen }: AppShellProps) {
  const { theme } = useTheme();
  const [view, setView] = useState<ShellView>("workflow");
  const [activeRunId, setActiveRunId] = useState<string | null>(null);
  const [provisionError, setProvisionError] = useState<string | null>(null);

  // Mirror /workspace/* into AppContext so Sidebar + ContextBar see the
  // live state regardless of which view is currently mounted.
  useWorkspaceContextSync();

  // 002-dsa-hub-pinnacle US3 — pill click → POST /workflow/provision →
  // navigate to Build. v1 redundancy gate is a soft pass-through (Phase 8
  // hardens it).
  async function startProvisioning(prdJson: unknown): Promise<void> {
    setProvisionError(null);
    const r = await fetch(`${BACKEND_URL}/workflow/provision`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-DSA-Session-ID": getOrMintSessionId(),
      },
      body: JSON.stringify({ prd: prdJson, redundancy_cleared: true }),
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
        ) : (
          /* Multi-source workspace (US1) */
          <div className="flex-1 min-h-0 overflow-y-auto">
            <Connections />
          </div>
        )}
      </main>
    </div>
  );
}
