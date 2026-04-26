import { useMemo } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  type Node,
  type Edge,
} from "@xyflow/react";
import { useAppState } from "../../context/AppContext";
import { useTheme } from "../../context/ThemeContext";
import { buildSourceGraph, buildERDGraph, buildLineageGraph, buildFieldGraph } from "../../lib/graph-utils";
import EntityNode from "./graph/EntityNode";
import SourceNode from "./graph/SourceNode";
import EmptyState from "../shared/EmptyState";
import type { StepNumber } from "../../lib/types";

interface GraphViewProps {
  stepNumber: StepNumber;
}

const nodeTypes = {
  entityNode: EntityNode,
  sourceNode: SourceNode,
};

export default function GraphView({ stepNumber }: GraphViewProps) {
  const { state } = useAppState();
  const { theme } = useTheme();

  const graphData = useMemo((): { nodes: Node[]; edges: Edge[] } | null => {
    switch (stepNumber) {
      case 1: {
        const prd = state.artifacts.prd;
        if (!prd.source_systems || prd.source_systems.length === 0) return null;
        return buildSourceGraph(prd, state.sourceContext?.productName);
      }
      case 2: {
        const model = state.artifacts.conceptual;
        if (!model || model.entities.length === 0) return null;
        return buildERDGraph(model);
      }
      case 3: {
        const model = state.artifacts.logical;
        if (!model || model.entities.length === 0) return null;
        return buildLineageGraph(model);
      }
      case 4: {
        const model = state.artifacts.detailed;
        if (!model) return null;
        return buildFieldGraph(model);
      }
      default:
        return null;
    }
  }, [stepNumber, state.artifacts, state.sourceContext]);

  if (!graphData) {
    return <EmptyState stepNumber={stepNumber} tabName="Visual" />;
  }

  return (
    <div className="flex-1" style={{ minHeight: "400px" }}>
      <ReactFlow
        nodes={graphData.nodes}
        edges={graphData.edges}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.3 }}
        proOptions={{ hideAttribution: true }}
        style={{ backgroundColor: theme.colors.white }}
      >
        <Background color={theme.colors.borderSubtle} gap={20} size={1} />
        <Controls
          style={{
            backgroundColor: theme.colors.white,
            borderColor: theme.colors.borderSubtle,
            borderRadius: "8px",
          }}
        />
      </ReactFlow>
    </div>
  );
}
