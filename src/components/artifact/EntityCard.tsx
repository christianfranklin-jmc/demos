import { useTheme } from "../../context/ThemeContext";
import type { ConceptualEntity } from "../../lib/types";
import { ENTITY_COLORS } from "../../lib/constants";

interface EntityCardProps {
  entity: ConceptualEntity;
}

export default function EntityCard({ entity }: EntityCardProps) {
  const { theme } = useTheme();
  const borderColor = ENTITY_COLORS[entity.role] || theme.colors.borderSubtle;

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
          <span className="text-sm font-medium" style={{ color: theme.colors.textPrimary }}>
            {entity.entity_name}
          </span>
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
        <p className="text-xs mb-2" style={{ color: theme.colors.textSecondary }}>
          {entity.description}
        </p>
        <div className="flex flex-col gap-1">
          {entity.abstract_attributes.map((attr, i) => (
            <span key={i} className="text-xs" style={{ color: theme.colors.textTertiary }}>
              &bull; {attr}
            </span>
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
