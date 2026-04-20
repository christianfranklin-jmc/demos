/**
 * EditableCell — Inline editable table cell.
 * Click to edit, blur/Enter to save, Escape to cancel.
 * Supports text input and select dropdowns.
 */

import { useState, useRef, useEffect } from "react";
import { useTheme } from "../../context/ThemeContext";

interface EditableCellProps {
  value: string;
  onSave: (value: string) => void;
  type?: "text" | "select";
  options?: string[];       // for select type
  mono?: boolean;           // monospace font
  className?: string;
  onValidate?: (value: string) => void;
}

export default function EditableCell({
  value,
  onSave,
  type = "text",
  options,
  mono = false,
  className = "",
  onValidate,
}: EditableCellProps) {
  const { theme } = useTheme();
  const [editing, setEditing] = useState(false);
  const [editValue, setEditValue] = useState(value);
  const inputRef = useRef<HTMLInputElement | HTMLSelectElement>(null);

  useEffect(() => {
    if (editing) inputRef.current?.focus();
  }, [editing]);

  if (!theme.features.enableInlineEdit) {
    return (
      <span
        className={className}
        style={{
          fontFamily: mono ? theme.typography.monoFamily : undefined,
          color: value ? theme.colors.textPrimary : theme.colors.textTertiary,
        }}
      >
        {value || "\u2014"}
      </span>
    );
  }

  const startEdit = () => {
    setEditValue(value);
    setEditing(true);
  };

  const save = () => {
    setEditing(false);
    if (editValue !== value) {
      onSave(editValue);
      if (onValidate) onValidate(editValue);
    }
  };

  const cancel = () => {
    setEditing(false);
    setEditValue(value);
  };

  if (editing) {
    if (type === "select" && options) {
      return (
        <select
          ref={inputRef as React.RefObject<HTMLSelectElement>}
          value={editValue}
          onChange={(e) => { setEditValue(e.target.value); }}
          onBlur={save}
          className="text-xs outline-none border rounded px-1 py-0.5"
          style={{
            borderColor: theme.colors.accent,
            color: theme.colors.textPrimary,
            backgroundColor: theme.colors.white,
          }}
        >
          {options.map((opt) => (
            <option key={opt} value={opt}>{opt}</option>
          ))}
        </select>
      );
    }

    return (
      <input
        ref={inputRef as React.RefObject<HTMLInputElement>}
        type="text"
        value={editValue}
        onChange={(e) => setEditValue(e.target.value)}
        onBlur={save}
        onKeyDown={(e) => {
          if (e.key === "Enter") save();
          if (e.key === "Escape") cancel();
        }}
        className="text-xs outline-none border-b w-full"
        style={{
          borderColor: theme.colors.accent,
          color: theme.colors.textPrimary,
          fontFamily: mono ? theme.typography.monoFamily : undefined,
          backgroundColor: "transparent",
        }}
      />
    );
  }

  return (
    <span
      onClick={startEdit}
      className={`cursor-pointer hover:underline ${className}`}
      style={{
        fontFamily: mono ? theme.typography.monoFamily : undefined,
        color: value ? theme.colors.textPrimary : theme.colors.textTertiary,
        textDecorationColor: theme.colors.accent,
      }}
      title="Click to edit"
    >
      {value || "\u2014"}
    </span>
  );
}
