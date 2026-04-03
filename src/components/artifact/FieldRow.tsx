import { useState, useEffect, useRef } from "react";
import { useTheme } from "../../context/ThemeContext";

interface FieldRowProps {
  label: string;
  value: string | string[] | null;
  onUpdate?: (value: string) => void;
  highlightKey?: string;
}

export default function FieldRow({ label, value, onUpdate, highlightKey }: FieldRowProps) {
  const { theme } = useTheme();
  const [editing, setEditing] = useState(false);
  const [editValue, setEditValue] = useState("");
  const [highlighted, setHighlighted] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const prevHighlightKey = useRef(highlightKey);

  // Highlight animation when value changes
  useEffect(() => {
    if (
      theme.features.showFieldHighlightAnimation &&
      highlightKey &&
      highlightKey !== prevHighlightKey.current &&
      value !== null
    ) {
      setHighlighted(true);
      const timer = setTimeout(() => setHighlighted(false), 300);
      prevHighlightKey.current = highlightKey;
      return () => clearTimeout(timer);
    }
    prevHighlightKey.current = highlightKey;
  }, [highlightKey, value, theme.features.showFieldHighlightAnimation]);

  // Focus input on edit
  useEffect(() => {
    if (editing) inputRef.current?.focus();
  }, [editing]);

  const startEdit = () => {
    if (!theme.features.enableInlineEdit || !onUpdate) return;
    const current = Array.isArray(value) ? value.join(", ") : (value ?? "");
    setEditValue(current);
    setEditing(true);
  };

  const saveEdit = () => {
    setEditing(false);
    if (onUpdate && editValue.trim() !== (Array.isArray(value) ? value.join(", ") : (value ?? ""))) {
      onUpdate(editValue.trim());
    }
  };

  const cancelEdit = () => {
    setEditing(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") saveEdit();
    if (e.key === "Escape") cancelEdit();
  };

  const isEmpty = value === null || value === "" || (Array.isArray(value) && value.length === 0);

  const displayValue = Array.isArray(value) ? value.join(", ") : value;

  return (
    <div
      className="group py-1.5 px-1 rounded transition-colors"
      style={{
        backgroundColor: highlighted ? theme.colors.accentSurface : "transparent",
        transition: "background-color 300ms ease",
      }}
    >
      <p
        className="text-xs font-medium uppercase tracking-wide mb-0.5"
        style={{ color: theme.colors.textSecondary }}
      >
        {label}
      </p>

      {editing ? (
        <input
          ref={inputRef}
          type="text"
          value={editValue}
          onChange={(e) => setEditValue(e.target.value)}
          onBlur={saveEdit}
          onKeyDown={handleKeyDown}
          className="w-full text-sm bg-transparent outline-none border-b"
          style={{
            color: theme.colors.textPrimary,
            borderColor: theme.colors.accent,
          }}
        />
      ) : (
        <div className="flex items-center gap-2">
          <p
            className="text-sm flex-1"
            style={{
              color: isEmpty ? theme.colors.textTertiary : theme.colors.textPrimary,
              fontStyle: isEmpty ? "italic" : "normal",
            }}
          >
            {isEmpty ? "Not captured yet" : displayValue}
          </p>

          {!isEmpty && theme.features.enableInlineEdit && onUpdate && (
            <button
              onClick={startEdit}
              className="opacity-0 group-hover:opacity-100 transition-opacity shrink-0"
              style={{ color: theme.colors.textSecondary, fontSize: "14px" }}
              title="Edit"
            >
              &#9998;
            </button>
          )}
        </div>
      )}
    </div>
  );
}
