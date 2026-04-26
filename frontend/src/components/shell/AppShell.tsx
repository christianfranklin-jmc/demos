import { useState } from "react";
import { useTheme } from "../../context/ThemeContext";
import { useWorkspaceContextSync } from "../../hooks/useWorkspaceContextSync";
import Sidebar from "./Sidebar";
import ContextBar from "./ContextBar";
import ChatPanel from "../chat/ChatPanel";
import ArtifactPanel from "../artifact/ArtifactPanel";
import Connections from "../../routes/Connections";

interface AppShellProps {
  onSettingsOpen: () => void;
}

// 002-dsa-hub-pinnacle US1: a tiny view-mode toggle so the new Connections
// page coexists with the existing 4-step workflow without a router.
export type ShellView = "workflow" | "connections";

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
