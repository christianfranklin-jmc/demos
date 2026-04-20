import { Handle, Position, type NodeProps } from "@xyflow/react";
import { useTheme } from "../../../context/ThemeContext";

interface SourceNodeData {
  label: string;
  type: string;
  domain?: string;
  quality?: number | null;
  [key: string]: unknown;
}

export default function SourceNode({ data }: NodeProps) {
  const { theme } = useTheme();
  const d = data as SourceNodeData;

  const isProduct = d.type === "product";
  const isTransform = d.type === "transform";

  return (
    <div
      className="rounded-lg border px-3 py-2"
      style={{
        borderColor: isProduct ? theme.colors.accent : theme.colors.borderSubtle,
        backgroundColor: isProduct
          ? theme.colors.accentSurface
          : isTransform
          ? theme.colors.surfaceInput
          : theme.colors.white,
        minWidth: "130px",
      }}
    >
      <Handle type="target" position={Position.Left} style={{ background: theme.colors.borderSubtle, width: 6, height: 6 }} />
      <div className="flex items-center gap-2">
        <span
          className="text-xs font-medium"
          style={{ color: theme.colors.textPrimary }}
        >
          {d.label}
        </span>
        {d.quality != null && (
          <span
            className="text-xs px-1 py-0.5 rounded"
            style={{
              backgroundColor: d.quality >= 70 ? theme.colors.accent + "20" : theme.colors.flagAmber + "20",
              color: d.quality >= 70 ? theme.colors.accent : theme.colors.flagAmber,
              fontSize: "9px",
              fontWeight: 600,
            }}
          >
            {d.quality}/100
          </span>
        )}
      </div>
      {d.domain && (
        <p className="text-xs" style={{ color: theme.colors.textTertiary, fontSize: "10px" }}>
          {d.domain}
        </p>
      )}
      <Handle type="source" position={Position.Right} style={{ background: theme.colors.borderSubtle, width: 6, height: 6 }} />
    </div>
  );
}
