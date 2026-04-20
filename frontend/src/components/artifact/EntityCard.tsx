import { useTheme } from "../../context/ThemeContext";
import EditableCell from "./EditableCell";
import type { ConceptualEntity } from "../../lib/types";
import { ENTITY_COLORS } from "../../lib/constants";

interface EntityCardProps {
  entity: ConceptualEntity;
  onUpdate?: (updates: Partial<ConceptualEntity>) => void;
  onValidate?: (fieldKey: string, value: any) => void;
}

export default function EntityCard({ entity, onUpdate, onValidate }: EntityCardProps) {
  const { theme } = useTheme();
  const borderColor = ENTITY_COLORS[entity.role] || theme.colors.borderSubtle;

  const handleAttrUpdate = (index: number, value: string) => {
    if (!onUpdate) return;
    const newAttrs = [...entity.abstract_attributes];
    newAttrs[index] = value;
    onUpdate({ abstract_attributes: newAttrs });
  };

  return (
    <div
      className="rounded-lg border overflow-hidden"
      style={{
        borderColor: theme.colors.borderSubtle,
        borderLeftWidth: "3px",
        borderLeftColor: borderColor,
        backgroundColor: theme.colors.white,
      }}
    >
      <div className="px-4 py-3">
        <div className="flex items-center gap-2 mb-2">
          <div
            className="w-7 h-7 rounded-md flex items-center justify-center text-xs font-bold"
            style={{
              backgroundColor: borderColor + "30",
              color: theme.colors.textPrimary,
            }}
          >
            {entity.entity_name.charAt(0).toUpperCase()}
          </div>
          {onUpdate ? (
            <EditableCell
              value={entity.entity_name}
              mono
              onSave={(v) => {
                onUpdate({ entity_name: v });
                if (onValidate) onValidate("entity_name", v);
              }}
              className="text-sm font-medium"
            />
          ) : (
            <span className="text-sm font-medium" style={{ color: theme.colors.textPrimary }}>
              {entity.entity_name}
            </span>
          )}
          <span
            className="text-xs px-1.5 py-0.5 rounded font-medium"
            style={{
              backgroundColor: borderColor + "30",
              color: theme.colors.textSecondary,
              fontSize: "10px",
            }}
          >
            {entity.role}
          </span>
        </div>

        {onUpdate ? (
          <EditableCell
            value={entity.description}
            onSave={(v) => onUpdate({ description: v })}
            className="text-xs mb-2 block"
          />
        ) : (
          <p className="text-xs mb-2" style={{ color: theme.colors.textSecondary }}>
            {entity.description}
          </p>
        )}

        <div className="flex flex-col gap-1">
          {entity.abstract_attributes.map((attr, i) => (
            <div key={i} className="flex items-start gap-1">
              <span className="text-xs" style={{ color: theme.colors.textTertiary }}>&bull;</span>
              {onUpdate ? (
                <EditableCell
                  value={attr}
                  onSave={(v) => handleAttrUpdate(i, v)}
                  className="text-xs"
                />
              ) : (
                <span className="text-xs" style={{ color: theme.colors.textTertiary }}>
                  {attr}
                </span>
              )}
            </div>
          ))}
        </div>

        {entity.cardinality_hint && (
          <p className="text-xs mt-2 italic" style={{ color: theme.colors.textTertiary }}>
            {entity.cardinality_hint}
          </p>
        )}
      </div>
    </div>
  );
}
