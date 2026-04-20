import { useTheme } from "../../context/ThemeContext";
import Sidebar from "./Sidebar";
import ContextBar from "./ContextBar";
import ChatPanel from "../chat/ChatPanel";
import ArtifactPanel from "../artifact/ArtifactPanel";

interface AppShellProps {
  onSettingsOpen: () => void;
}

export default function AppShell({ onSettingsOpen }: AppShellProps) {
  const { theme } = useTheme();

  return (
    <div className="flex h-screen w-screen overflow-hidden" style={{ backgroundColor: theme.colors.white }}>
      <Sidebar onSettingsOpen={onSettingsOpen} />

      <main className="flex-1 flex flex-col min-w-0">
        <ContextBar />

        {/* Split Panel Area */}
        <div className="flex-1 flex min-h-0">
          <ChatPanel />
          <ArtifactPanel />
        </div>
      </main>
    </div>
  );
}
