import { useTheme } from "../../context/ThemeContext";
import type { ConversationMessage } from "../../lib/types";

interface MessageBubbleProps {
  message: ConversationMessage;
}

export default function MessageBubble({ message }: MessageBubbleProps) {
  const { theme } = useTheme();

  if (message.message_role === "system") {
    return (
      <div className="flex justify-center px-4 py-2">
        <p
          className="text-xs italic text-center"
          style={{ color: theme.colors.textTertiary }}
        >
          {message.message_text}
        </p>
      </div>
    );
  }

  const isAgent = message.message_role === "agent";

  return (
    <div
      className={`flex ${isAgent ? "justify-start" : "justify-end"} px-4 py-1.5`}
    >
      {isAgent && (
        <div
          className="w-6 h-6 rounded-full flex items-center justify-center shrink-0 mr-2 mt-1"
          style={{
            backgroundColor: theme.colors.surfaceActiveNav,
            color: theme.colors.textPrimary,
            fontSize: "9px",
            fontWeight: 600,
          }}
        >
          {theme.agent.avatarLabel}
        </div>
      )}
      <div
        className="text-sm"
        style={{
          maxWidth: "88%",
          padding: "10px 14px",
          borderRadius: "10px",
          lineHeight: 1.6,
          whiteSpace: "pre-wrap",
          color: theme.colors.textPrimary,
          ...(isAgent
            ? {
                backgroundColor: theme.colors.white,
                border: `1px solid ${theme.colors.borderSubtle}`,
              }
            : {
                backgroundColor: theme.colors.surfaceInput,
              }),
        }}
      >
        {message.message_text}
      </div>
    </div>
  );
}
