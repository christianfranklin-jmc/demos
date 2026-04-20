/**
 * DSA MVP — App Root
 *
 * Manages session-level concerns (settings panel, keyboard shortcuts).
 * Layout is delegated to AppShell.
 */

import { useState, useEffect } from "react";
import { useTheme } from "./context/ThemeContext";
import AppShell from "./components/shell/AppShell";
import SettingsPanel from "./components/shared/SettingsPanel";

export default function App() {
  const { theme } = useTheme();
  const [settingsOpen, setSettingsOpen] = useState(false);

  // Keyboard shortcut: Ctrl+Shift+S to toggle settings
  useEffect(() => {
    if (!theme.features.enableKeyboardShortcuts) return;
    const handler = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key === "S") {
        e.preventDefault();
        setSettingsOpen((prev) => !prev);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [theme.features.enableKeyboardShortcuts]);

  return (
    <>
      <AppShell onSettingsOpen={() => setSettingsOpen(true)} />
      <SettingsPanel isOpen={settingsOpen} onClose={() => setSettingsOpen(false)} />
    </>
  );
}
