// SemanticGraph — force-directed entity/join visualization (T109, US5).
//
// Uses React Flow with an auto-layout heuristic — entities arranged in a
// circle, joins drawn as edges. Selecting a node calls back so the parent
// page can show the EntityPanel.

import { useMemo } from "react";
import {
  Background,
  Controls,
  Handle,
  Position,
  ReactFlow,
  type Edge,
  type Node,
  type NodeProps,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";

import { useTheme } from "../../context/ThemeContext";
import type {
  Cardinality,
  GraphEntityRow,
  GraphJoinRow,
} from "../../hooks/useSemanticGraph";

interface Props {
  entities: GraphEntityRow[];
  joins: GraphJoinRow[];
  selectedEntityId: string | null;
  onSelect: (entity_id: string | null) => void;
}

interface EntityNodeData extends Record<string, unknown> {
  row: GraphEntityRow;
  selected: boolean;
}

const DOMAIN_COLOR: Record<string, string> = {
  wealth_mgmt: "#2563EB",
  accounting: "#0D9488",
  crm: "#F97316",
  hr: "#A855F7",
  planning: "#EAB308",
  unspecified: "#94A3B8",
};

function EntityNode({ data }: NodeProps) {
  const { theme } = useTheme();
  const { row, selected } = data as EntityNodeData;
  const ring = DOMAIN_COLOR[row.domain] ?? theme.colors.borderSubtle;
  return (
    <div
      data-testid="entity-node"
      data-entity-id={row.entity_id}
      data-selected={selected ? "true" : "false"}
      className="rounded-lg px-3 py-2 cursor-pointer"
      style={{
        backgroundColor: theme.colors.surfaceSubtle,
        border: `2px solid ${selected ? theme.colors.accent : ring}`,
        color: theme.colors.textPrimary,
        boxShadow: selected ? `0 0 0 2px ${theme.colors.accent}40` : undefined,
        minWidth: 140,
      }}
    >
      <Handle type="target" position={Position.Left} style={{ opacity: 0.3 }} />
      <div className="font-semibold text-sm truncate">{row.name}</div>
      <div
        className="text-[10px] uppercase tracking-wide"
        style={{ color: theme.colors.textTertiary }}
      >
        {row.domain.replace("_", " ")}
      </div>
      <div
        className="text-[10px] tabular-nums"
        style={{ color: theme.colors.textSecondary }}
      >
        {row.metric_count} metric · {row.binding_count} binding
      </div>
      <Handle type="source" position={Position.Right} style={{ opacity: 0.3 }} />
    </div>
  );
}

const NODE_TYPES = { entity: EntityNode };

const CARD_LABEL: Record<Cardinality, string> = {
  one_to_one: "1:1",
  one_to_many: "1:N",
  many_to_many: "N:N",
};

/** Lay nodes out on a circle so the graph is readable without a real layout engine. */
function circleLayout(count: number, index: number): { x: number; y: number } {
  const radius = Math.max(160, count * 30);
  const cx = radius + 40;
  const cy = radius + 40;
  if (count === 1) return { x: cx, y: cy };
  const angle = (2 * Math.PI * index) / count - Math.PI / 2;
  return {
    x: cx + Math.cos(angle) * radius,
    y: cy + Math.sin(angle) * radius,
  };
}

export default function SemanticGraph({
  entities,
  joins,
  selectedEntityId,
  onSelect,
}: Props) {
  const nodes = useMemo<Node[]>(() => {
    return entities.map((row, i) => {
      const data: EntityNodeData = {
        row,
        selected: row.entity_id === selectedEntityId,
      };
      return {
        id: row.entity_id,
        type: "entity",
        position: circleLayout(entities.length, i),
        data,
        draggable: true,
      };
    });
  }, [entities, selectedEntityId]);

  const edges = useMemo<Edge[]>(() => {
    return joins.map((j) => ({
      id: j.join_id,
      source: j.left_entity_id,
      target: j.right_entity_id,
      type: "smoothstep",
      label: CARD_LABEL[j.cardinality],
      style: {
        stroke: "var(--theme-border-subtle, #2A2A3E)",
        strokeWidth: 1.5,
      },
      labelBgStyle: { fill: "var(--theme-surface-subtle, #16213E)" },
    }));
  }, [joins]);

  return (
    <div
      data-testid="semantic-graph"
      className="rounded-lg overflow-hidden"
      style={{ height: 420, border: `1px solid var(--theme-border-subtle, #2A2A3E)` }}
    >
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={NODE_TYPES}
        onNodeClick={(_, node) => onSelect(node.id)}
        onPaneClick={() => onSelect(null)}
        fitView
        proOptions={{ hideAttribution: true }}
      >
        <Background gap={16} size={1} />
        <Controls showInteractive={false} />
      </ReactFlow>
    </div>
  );
}
