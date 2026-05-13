import { useState, useRef, useEffect } from "react";
import { useTheme } from "../../context/ThemeContext";

interface ChatInputProps {
  onSend: (text: string, imageData?: string) => void;
  disabled?: boolean;
}

export default function ChatInput({ onSend, disabled = false }: ChatInputProps) {
  const { theme } = useTheme();
  const [value, setValue] = useState("");
  const [imageData, setImageData] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const canSend = !disabled && (value.trim().length > 0 || imageData !== null);

  const handleSend = () => {
    if (!canSend) return;
    const text = value.trim() || (imageData ? "Analyze this dashboard" : "");
    onSend(text, imageData ?? undefined);
    setValue("");
    setImageData(null);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (ev) => setImageData(ev.target?.result as string);
    reader.readAsDataURL(file);
    e.target.value = "";
  };

  useEffect(() => {
    if (!disabled) inputRef.current?.focus();
  }, [disabled]);

  return (
    <div className="p-3">
      {/* Image preview strip */}
      {imageData && (
        <div className="flex items-center gap-2 mb-2 px-1">
          <img
            src={imageData}
            alt="dashboard preview"
            className="h-12 w-auto rounded object-cover"
            style={{ border: `1px solid ${theme.colors.borderSubtle}` }}
          />
          <button
            onClick={() => setImageData(null)}
            className="text-xs leading-none"
            style={{ color: theme.colors.textTertiary }}
          >
            ✕ remove
          </button>
        </div>
      )}

      <div
        className="flex items-center gap-2 px-4 py-2.5"
        style={{
          backgroundColor: theme.colors.surfaceInput,
          borderRadius: `${theme.layout.borderRadius.input}px`,
        }}
      >
        {/* Hidden file input */}
        <input
          ref={fileInputRef}
          type="file"
          accept="image/*"
          className="hidden"
          onChange={handleFileChange}
        />

        {/* Image upload trigger */}
        <button
          onClick={() => fileInputRef.current?.click()}
          disabled={disabled}
          title="Attach a dashboard screenshot"
          className="shrink-0 transition-opacity select-none"
          style={{
            fontSize: "15px",
            lineHeight: 1,
            color: imageData ? theme.colors.btnPrimaryBg : theme.colors.textTertiary,
            opacity: disabled ? 0.4 : 1,
          }}
        >
          &#128247;
        </button>

        <input
          ref={inputRef}
          type="text"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={
            imageData
              ? "Add a note, or send to analyze..."
              : theme.agent.inputPlaceholder
          }
          disabled={disabled}
          className="flex-1 bg-transparent outline-none text-sm"
          style={{ color: theme.colors.textPrimary }}
        />

        <button
          onClick={handleSend}
          disabled={!canSend}
          className="w-7 h-7 rounded-full flex items-center justify-center shrink-0 transition-opacity"
          style={{
            backgroundColor: theme.colors.btnPrimaryBg,
            opacity: canSend ? 1 : 0.4,
          }}
        >
          <span style={{ color: theme.colors.btnPrimaryText, fontSize: "12px" }}>&uarr;</span>
        </button>
      </div>
    </div>
  );
}
