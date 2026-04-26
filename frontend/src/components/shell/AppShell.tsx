import { useState } from "react";
import { useTheme } from "../../context/ThemeContext";
import { useWorkspaceContextSync } from "../../hooks/useWorkspaceContextSync";
import Sidebar from "./Sidebar";
import ContextBar from "./ContextBar";
import ChatPanel from "../chat/ChatPanel";
import ArtifactPanel from "../artifact/ArtifactPanel";
import Connections from "../../routes/Connections";
import Step1Discovery from "../../routes/Step1Discovery";

interface AppShellProps {
  onSettingsOpen: () => void;
}

// 002-dsa-hub-pinnacle US1+US2: view-mode toggle so the new Connections page
// and the new Step-1 Discovery page coexist with the existing 4-step
// workflow without a router.
export type ShellView = "workflow" | "connections" | "discovery";

export default function AppShell({ onSettingsOpen }: AppShellProps) {
  const { theme } = useTheme();
  const [view, setView] = useState<ShellView>("workflow");

  // Mirror /workspace/* into AppContext so Sidebar + ContextBar see the
  // live state regardless of which view is currently mounted.
  useWorkspaceContextSync();

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
            <Step1Discovery
              onPillAccepted={(pill, prd) => {
                // T063 follow-up: forward pill_id + prd to Step 2. For now
                // log the handoff so the click path is observable.
                // eslint-disable-next-line no-console
                console.info(
                  "[US2] pill accepted",
                  pill.pill_id,
                  pill.title,
                  "→ prd",
                  prd.prd_id
                );
                setView("workflow");
              }}
            />
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
