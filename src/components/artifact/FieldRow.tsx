import { useState, useEffect, useRef } from "react";
import { useTheme } from "../../context/ThemeContext";
import { useAppState } from "../../context/AppContext";

interface FieldRowProps {
  label: string;
  value: string | string[] | null;
  fieldType?: "string" | "string_array" | "object_display";
  fieldKey?: string;  // for standards validation lookup
  onUpdate?: (value: string) => void;
  onArrayUpdate?: (value: string[]) => void;
  onValidate?: (fieldKey: string, value: any) => void;
  highlightKey?: string;
}

export default function FieldRow({
  label,
  value,
  fieldType = "string",
  fieldKey,
  onUpdate,
  onArrayUpdate,
  onValidate,
  highlightKey,
}: FieldRowProps) {
  const { theme } = useTheme();
  const { state } = useAppState();
  const [editing, setEditing] = useState(false);
  const [editValue, setEditValue] = useState("");
  const [highlighted, setHighlighted] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const prevHighlightKey = useRef(highlightKey);

  // Check for active standards flags on this field
  const hasStandardsFlag = fieldKey
    ? state.flags.some(
        (f) =>
          f.status === "open" &&
          f.flag_type.startsWith("standards_") &&
          f.description.toLowerCase().includes(label.toLowerCase().slice(0, 10))
      )
    : false;

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

  useEffect(() => {
    if (editing) inputRef.current?.focus();
  }, [editing]);

  const startEdit = () => {
    if (!theme.features.enableInlineEdit) return;
    if (fieldType === "object_display") return;
    if (!onUpdate && !onArrayUpdate) return;

    const current = Array.isArray(value) ? value.join(", ") : (value ?? "");
    setEditValue(current);
    setEditing(true);
  };

  const saveEdit = () => {
    setEditing(false);
    const trimmed = editValue.trim();
    const oldValue = Array.isArray(value) ? value.join(", ") : (value ?? "");

    if (trimmed === oldValue) return;

    if (fieldType === "string_array" && onArrayUpdate) {
      const arr = trimmed.split(",").map((s) => s.trim()).filter(Boolean);
      onArrayUpdate(arr);
      if (onValidate && fieldKey) onValidate(fieldKey, arr);
    } else if (onUpdate) {
      onUpdate(trimmed);
      if (onValidate && fieldKey) onValidate(fieldKey, trimmed);
    }
  };

  const cancelEdit = () => setEditing(false);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") saveEdit();
    if (e.key === "Escape") cancelEdit();
  };

  const isEmpty = value === null || value === "" || (Array.isArray(value) && value.length === 0);
  const displayValue = Array.isArray(value) ? value.join(", ") : value;
  const canEdit = theme.features.enableInlineEdit && fieldType !== "object_display" && (onUpdate || onArrayUpdate);

  return (
    <div
      className="group py-1.5 px-1 rounded transition-colors"
      style={{
        backgroundColor: highlighted ? theme.colors.accentSurface : "transparent",
        transition: "background-color 300ms ease",
      }}
    >
      <div className="flex items-center gap-2">
        <p
          className="text-xs font-medium uppercase tracking-wide mb-0.5"
          style={{ color: theme.colors.textSecondary }}
        >
          {label}
        </p>
        {hasStandardsFlag && (
          <span
            className="text-xs px-1.5 py-0.5 rounded"
            style={{
              backgroundColor: theme.colors.flagPurpleSurface || "#EDE9FE",
              color: theme.colors.flagPurple || "#8B5CF6",
              fontSize: "9px",
              fontWeight: 600,
            }}
          >
            ! Standards
          </span>
        )}
      </div>

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

          {!isEmpty && canEdit && (
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
