import { Handle, Position, type NodeProps } from "@xyflow/react";
import { useTheme } from "../../../context/ThemeContext";

interface EntityNodeData {
  label: string;
  role: string;
  description: string;
  attributes: string[];
  color: string;
  [key: string]: unknown;
}

export default function EntityNode({ data }: NodeProps) {
  const { theme } = useTheme();
  const d = data as EntityNodeData;

  return (
    <div
      className="rounded-lg border overflow-hidden"
      style={{
        borderColor: theme.colors.borderSubtle,
        borderLeftWidth: "3px",
        borderLeftColor: d.color,
        backgroundColor: theme.colors.white,
        minWidth: "160px",
        maxWidth: "220px",
      }}
    >
      <Handle type="target" position={Position.Top} style={{ background: d.color, width: 8, height: 8 }} />
      <div className="px-3 py-2">
        <div className="flex items-center gap-1.5 mb-1">
          <span className="text-xs font-medium" style={{ color: theme.colors.textPrimary }}>
            {d.label}
          </span>
          <span
            className="text-xs px-1 py-0.5 rounded"
            style={{ backgroundColor: d.color + "30", color: theme.colors.textSecondary, fontSize: "9px", fontWeight: 600 }}
          >
            {d.role}
          </span>
        </div>
        <p className="text-xs mb-1" style={{ color: theme.colors.textTertiary, fontSize: "10px" }}>
          {d.description}
        </p>
        {d.attributes && d.attributes.length > 0 && (
          <div className="flex flex-col">
            {d.attributes.slice(0, 3).map((attr: string, i: number) => (
              <span key={i} className="text-xs" style={{ color: theme.colors.textTertiary, fontSize: "10px" }}>
                &bull; {attr}
              </span>
            ))}
            {d.attributes.length > 3 && (
              <span className="text-xs" style={{ color: theme.colors.textTertiary, fontSize: "10px" }}>
                +{d.attributes.length - 3} more
              </span>
            )}
          </div>
        )}
      </div>
      <Handle type="source" position={Position.Bottom} style={{ background: d.color, width: 8, height: 8 }} />
    </div>
  );
}
