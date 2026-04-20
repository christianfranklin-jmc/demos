import { useState, useRef, useEffect } from "react";
import { useTheme } from "../../context/ThemeContext";

interface ChatInputProps {
  onSend: (text: string) => void;
  disabled?: boolean;
}

export default function ChatInput({ onSend, disabled = false }: ChatInputProps) {
  const { theme } = useTheme();
  const [value, setValue] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  const handleSend = () => {
    const trimmed = value.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setValue("");
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  // Refocus after send (when disabled toggles back to false)
  useEffect(() => {
    if (!disabled) {
      inputRef.current?.focus();
    }
  }, [disabled]);

  return (
    <div className="p-3">
      <div
        className="flex items-center gap-2 px-4 py-2.5"
        style={{
          backgroundColor: theme.colors.surfaceInput,
          borderRadius: `${theme.layout.borderRadius.input}px`,
        }}
      >
        <span style={{ color: theme.colors.textTertiary, fontSize: "14px" }}>&#9889;</span>
        <input
          ref={inputRef}
          type="text"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={theme.agent.inputPlaceholder}
          disabled={disabled}
          className="flex-1 bg-transparent outline-none text-sm"
          style={{ color: theme.colors.textPrimary }}
        />
        <button
          onClick={handleSend}
          disabled={disabled || !value.trim()}
          className="w-7 h-7 rounded-full flex items-center justify-center shrink-0 transition-opacity"
          style={{
            backgroundColor: theme.colors.btnPrimaryBg,
            opacity: value.trim() ? 1 : 0.4,
          }}
        >
          <span style={{ color: theme.colors.btnPrimaryText, fontSize: "12px" }}>&uarr;</span>
        </button>
      </div>
    </div>
  );
}
