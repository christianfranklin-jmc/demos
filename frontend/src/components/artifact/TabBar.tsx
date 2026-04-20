import { useTheme } from "../../context/ThemeContext";

interface TabBarProps {
  tabs: string[];
  activeTab: string;
  onTabChange: (tab: string) => void;
}

export default function TabBar({ tabs, activeTab, onTabChange }: TabBarProps) {
  const { theme } = useTheme();

  return (
    <div
      className="flex items-center gap-4 px-4 border-b shrink-0"
      style={{
        height: "40px",
        backgroundColor: theme.colors.surfaceSubtle,
        borderColor: theme.colors.borderSubtle,
      }}
    >
      {tabs.map((tab) => {
        const isActive = tab === activeTab;
        return (
          <button
            key={tab}
            onClick={() => onTabChange(tab)}
            className="text-xs font-medium h-full relative"
            style={{
              color: isActive ? theme.colors.textPrimary : theme.colors.textSecondary,
            }}
          >
            {tab}
            {isActive && (
              <span
                className="absolute bottom-0 left-0 right-0 h-0.5"
                style={{ backgroundColor: theme.colors.accent }}
              />
            )}
          </button>
        );
      })}
    </div>
  );
}
