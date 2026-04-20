import { useTheme } from "../../context/ThemeContext";

export default function TypingIndicator() {
  const { theme } = useTheme();

  return (
    <div className="flex items-start gap-2 px-4 py-2">
      {/* Agent avatar badge */}
      <div
        className="w-6 h-6 rounded-full flex items-center justify-center shrink-0 text-xs font-semibold"
        style={{
          backgroundColor: theme.colors.surfaceActiveNav,
          color: theme.colors.textPrimary,
          fontSize: "9px",
        }}
      >
        {theme.agent.avatarLabel}
      </div>

      {/* Dots container */}
      <div
        className="flex items-center gap-1 px-3 py-2"
        style={{
          backgroundColor: theme.colors.white,
          border: `1px solid ${theme.colors.borderSubtle}`,
          borderRadius: "10px",
        }}
      >
        {[0, 1, 2].map((i) => (
          <span
            key={i}
            className="w-1.5 h-1.5 rounded-full"
            style={{
              backgroundColor: theme.colors.textTertiary,
              animation: `typing-dot 1.4s infinite`,
              animationDelay: `${i * 150}ms`,
            }}
          />
        ))}
        <style>{`
          @keyframes typing-dot {
            0%, 60%, 100% { opacity: 0.3; transform: scale(0.8); }
            30% { opacity: 1; transform: scale(1); }
          }
        `}</style>
      </div>
    </div>
  );
}
