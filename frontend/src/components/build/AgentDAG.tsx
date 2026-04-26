// AgentDAG — React Flow visualization of the 7-agent provisioning DAG (T083, US3).
//
// One node per agent in DAG_ORDER, with the dependency edges from
// provisioning/orchestrator.py. Active agents pulse; completed agents
// show a check + artifact count; failed agents render in error red
// with a Retry button (uses the orchestrator's per-agent retry path).

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
import type { AgentSnapshot } from "../../hooks/useProvisioningRun";
import { AGENT_ORDER } from "../../hooks/useProvisioningRun";
import type { AgentId } from "../../lib/agentcore-client/parsers/v2";

interface Props {
  agents: AgentSnapshot[];
  onRetry: (agent_id: AgentId) => void | Promise<void>;
}

// Status color tokens — see ADR-020 D4 + research.md R10.
// T089 adds CSS custom properties; these are the canonical literals.
const STATUS_SUCCESS = "var(--status-success, #16A34A)";
const STATUS_ERROR = "var(--status-error, #DC2626)";

// Visual layout: linear chain except semantic + delivery diverge after mapping.
// Coordinates are tuned for a 920×260 viewport.
const NODE_POS: Record<AgentId, { x: number; y: number }> = {
  schema:   { x:   0, y: 80 },
  pipeline: { x: 160, y: 80 },
  model:    { x: 320, y: 80 },
  quality:  { x: 480, y: 80 },
  mapping:  { x: 640, y: 80 },
  semantic: { x: 800, y:  0 },
  delivery: { x: 800, y: 160 },
};

const DAG_EDGES: [AgentId, AgentId][] = [
  ["schema", "pipeline"],
  ["pipeline", "model"],
  ["model", "quality"],
  ["quality", "mapping"],
  ["mapping", "semantic"],
  ["mapping", "delivery"],
  ["semantic", "delivery"],
];

const AGENT_LABEL: Record<AgentId, string> = {
  schema: "Schema",
  pipeline: "Pipeline",
  model: "Model",
  quality: "Quality",
  mapping: "Mapping",
  semantic: "Semantic",
  delivery: "Delivery",
};

const AGENT_ICON: Record<AgentId, string> = {
  schema: "🧬",
  pipeline: "🔁",
  model: "🪜",
  quality: "✅",
  mapping: "🧊",
  semantic: "🧭",
  delivery: "🚚",
};

interface AgentNodeData extends Record<string, unknown> {
  snapshot: AgentSnapshot;
  onRetry: (agent_id: AgentId) => void | Promise<void>;
}

function AgentNode({ data }: NodeProps) {
  const { theme } = useTheme();
  const { snapshot, onRetry } = data as AgentNodeData;
  const { state, message, artifacts, attempt, error_message } = snapshot;

  const ringColor =
    state === "completed"
      ? STATUS_SUCCESS
      : state === "failed"
        ? STATUS_ERROR
        : state === "active"
          ? theme.colors.accent
          : theme.colors.borderSubtle;

  const isActive = state === "active";

  return (
    <div
      data-testid="agent-node"
      data-agent-id={snapshot.agent_id}
      data-state={state}
      className={`flex flex-col gap-1 px-3 py-2 rounded-lg ${
        isActive ? "animate-pulse" : ""
      }`}
      style={{
        minWidth: 140,
        backgroundColor: theme.colors.surfaceSubtle,
        border: `2px solid ${ringColor}`,
        color: theme.colors.textPrimary,
      }}
    >
      <Handle type="target" position={Position.Left} style={{ opacity: 0.3 }} />
      <div className="flex items-center gap-2">
        <span aria-hidden>{AGENT_ICON[snapshot.agent_id]}</span>
        <span className="font-semibold text-sm">
          {AGENT_LABEL[snapshot.agent_id]}
        </span>
        {state === "completed" ? (
          <span style={{ color: STATUS_SUCCESS, marginLeft: "auto" }}>✓</span>
        ) : state === "failed" ? (
          <span style={{ color: STATUS_ERROR, marginLeft: "auto" }}>✗</span>
        ) : null}
      </div>
      <div
        className="text-[10px] flex items-center gap-1.5"
        style={{ color: theme.colors.textTertiary }}
      >
        <span className="uppercase tracking-wide">{state}</span>
        {attempt > 1 ? <span>· attempt {attempt}</span> : null}
      </div>
      {message ? (
        <div
          className="text-[11px] truncate max-w-[180px]"
          style={{ color: theme.colors.textSecondary }}
          title={message}
        >
          {message}
        </div>
      ) : null}
      {state === "completed" && artifacts.length > 0 ? (
        <div
          className="text-[10px]"
          style={{ color: theme.colors.textTertiary }}
        >
          {artifacts.length} artifact{artifacts.length === 1 ? "" : "s"}
        </div>
      ) : null}
      {state === "failed" && error_message ? (
        <div className="flex flex-col gap-1">
          <span
            className="text-[10px]"
            style={{ color: STATUS_ERROR }}
            title={error_message}
          >
            {truncate(error_message, 32)}
          </span>
          <button
            type="button"
            onClick={() => void onRetry(snapshot.agent_id)}
            className="text-[10px] px-1.5 py-0.5 rounded"
            style={{
              color: theme.colors.accent,
              border: `1px solid ${theme.colors.borderSubtle}`,
              alignSelf: "flex-start",
            }}
          >
            Retry
          </button>
        </div>
      ) : null}
      <Handle type="source" position={Position.Right} style={{ opacity: 0.3 }} />
    </div>
  );
}

function truncate(s: string, n: number): string {
  return s.length <= n ? s : s.slice(0, n - 1) + "…";
}

const NODE_TYPES = { agent: AgentNode };

export default function AgentDAG({ agents, onRetry }: Props) {
  const nodes = useMemo<Node[]>(() => {
    return AGENT_ORDER.map((aid) => {
      const snap = agents.find((a) => a.agent_id === aid);
      const data: AgentNodeData = {
        snapshot: snap ?? {
          agent_id: aid,
          state: "pending",
          attempt: 1,
          artifacts: [],
          message: null,
          error_code: null,
          error_message: null,
          latency_ms_p95: null,
          started_at: null,
          completed_at: null,
        },
        onRetry,
      };
      return {
        id: aid,
        type: "agent",
        position: NODE_POS[aid],
        data,
        draggable: false,
      };
    });
  }, [agents, onRetry]);

  const edges = useMemo<Edge[]>(() => {
    return DAG_EDGES.map(([from, to]) => {
      const fromAgent = agents.find((a) => a.agent_id === from);
      const isActiveEdge = fromAgent?.state === "active";
      const isCompletedEdge = fromAgent?.state === "completed";
      return {
        id: `${from}->${to}`,
        source: from,
        target: to,
        type: "smoothstep",
        animated: isActiveEdge,
        style: {
          stroke: isCompletedEdge ? STATUS_SUCCESS : "var(--theme-border-subtle, #2A2A3E)",
          strokeWidth: isCompletedEdge ? 2 : 1,
        },
      };
    });
  }, [agents]);

  return (
    <div
      data-testid="agent-dag"
      className="rounded-lg overflow-hidden"
      style={{ height: 280, border: `1px solid var(--theme-border-subtle, #2A2A3E)` }}
    >
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={NODE_TYPES}
        fitView
        nodesDraggable={false}
        nodesConnectable={false}
        zoomOnDoubleClick={false}
        proOptions={{ hideAttribution: true }}
      >
        <Background gap={16} size={1} />
        <Controls showInteractive={false} />
      </ReactFlow>
    </div>
  );
}
