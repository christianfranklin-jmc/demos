/**
 * Graph utilities — transforms artifact data into React Flow nodes and edges.
 */

import type { Node, Edge } from "@xyflow/react";
import type {
  PRDArtifact,
  ConceptualModelArtifact,
  LogicalModelArtifact,
  DetailedRequirementsArtifact,
} from "./types";
import { ENTITY_COLORS } from "./constants";

// ─── Step 1: Source System Graph ───

export function buildSourceGraph(
  prd: PRDArtifact,
  productName: string = "ROMI Data Product",
): { nodes: Node[]; edges: Edge[] } {
  const nodes: Node[] = [];
  const edges: Edge[] = [];

  // Center node: the data product (label from sourceContext when available).
  nodes.push({
    id: "product",
    type: "sourceNode",
    position: { x: 300, y: 200 },
    data: { label: productName, type: "product", quality: null },
  });

  const sources = prd.source_systems || [];
  const angleStep = (2 * Math.PI) / Math.max(sources.length, 1);
  const radius = 180;

  sources.forEach((source, i) => {
    const angle = angleStep * i - Math.PI / 2;
    nodes.push({
      id: `source-${i}`,
      type: "sourceNode",
      position: {
        x: 300 + radius * Math.cos(angle),
        y: 200 + radius * Math.sin(angle),
      },
      data: {
        label: source.system,
        type: "source",
        domain: source.data_domain,
        quality: source.access_confirmed ? 87 : null,
      },
    });
    edges.push({
      id: `e-source-${i}`,
      source: `source-${i}`,
      target: "product",
      animated: true,
      style: { stroke: "#3DDBB8", strokeWidth: 2 },
    });
  });

  return { nodes, edges };
}

// ─── Step 2: ERD Graph ───

export function buildERDGraph(model: ConceptualModelArtifact): { nodes: Node[]; edges: Edge[] } {
  const nodes: Node[] = [];
  const edges: Edge[] = [];

  // Position fact table in center, dimensions around it
  const facts = model.entities.filter((e) => e.role === "FACT");
  const dims = model.entities.filter((e) => e.role !== "FACT");

  facts.forEach((entity, i) => {
    nodes.push({
      id: entity.entity_id,
      type: "entityNode",
      position: { x: 300, y: 200 + i * 200 },
      data: {
        label: entity.entity_name,
        role: entity.role,
        description: entity.description,
        attributes: entity.abstract_attributes,
        color: ENTITY_COLORS[entity.role] || ENTITY_COLORS.PRIMARY,
      },
    });
  });

  const dimAngleStep = (2 * Math.PI) / Math.max(dims.length, 1);
  const dimRadius = 250;

  dims.forEach((entity, i) => {
    const angle = dimAngleStep * i - Math.PI / 2;
    nodes.push({
      id: entity.entity_id,
      type: "entityNode",
      position: {
        x: 300 + dimRadius * Math.cos(angle),
        y: 220 + dimRadius * Math.sin(angle),
      },
      data: {
        label: entity.entity_name,
        role: entity.role,
        description: entity.description,
        attributes: entity.abstract_attributes,
        color: ENTITY_COLORS[entity.role] || ENTITY_COLORS.PRIMARY,
      },
    });
  });

  model.relationships.forEach((rel, i) => {
    const sourceId = model.entities.find((e) => e.entity_name === rel.from_entity)?.entity_id;
    const targetId = model.entities.find((e) => e.entity_name === rel.to_entity)?.entity_id;
    if (sourceId && targetId) {
      edges.push({
        id: `rel-${i}`,
        source: sourceId,
        target: targetId,
        label: rel.verb,
        style: { stroke: "#3DDBB8", strokeWidth: 2 },
        labelStyle: { fontSize: 10, fill: "#6B6B6B" },
        labelBgStyle: { fill: "#FFFFFF", fillOpacity: 0.9 },
        labelBgPadding: [4, 2] as [number, number],
      });
    }
  });

  return { nodes, edges };
}

// ─── Step 3: Lineage Graph ───

export function buildLineageGraph(model: LogicalModelArtifact): { nodes: Node[]; edges: Edge[] } {
  const nodes: Node[] = [];
  const edges: Edge[] = [];

  const entity = model.entities[0];
  if (!entity) return { nodes, edges };

  // Source systems on the left
  const uniqueSources = new Set<string>();
  entity.attributes.forEach((attr) => {
    if (attr.source_field) {
      const source = attr.source_field.split(".")[0] || "Unknown";
      uniqueSources.add(source);
    }
  });

  const sources = Array.from(uniqueSources);
  sources.forEach((source, i) => {
    nodes.push({
      id: `src-${source}`,
      type: "sourceNode",
      position: { x: 0, y: i * 80 },
      data: { label: source, type: "source" },
    });
  });

  // Transform node in the middle
  nodes.push({
    id: "transform",
    type: "sourceNode",
    position: { x: 280, y: (sources.length * 80) / 2 - 30 },
    data: { label: "Transform & Map", type: "transform" },
  });

  // Target table on the right
  nodes.push({
    id: "target",
    type: "entityNode",
    position: { x: 530, y: (sources.length * 80) / 2 - 60 },
    data: {
      label: entity.entity_name,
      role: entity.role,
      description: `${entity.attributes.length} fields`,
      attributes: entity.attributes.slice(0, 3).map((a) => a.target_field),
      color: ENTITY_COLORS[entity.role] || ENTITY_COLORS.PRIMARY,
    },
  });

  // Source → Transform edges
  sources.forEach((source) => {
    edges.push({
      id: `e-${source}-transform`,
      source: `src-${source}`,
      target: "transform",
      animated: true,
      style: { stroke: "#9CA3AF", strokeWidth: 1.5 },
    });
  });

  // Transform → Target edge
  edges.push({
    id: "e-transform-target",
    source: "transform",
    target: "target",
    animated: true,
    style: { stroke: "#3DDBB8", strokeWidth: 2 },
  });

  return { nodes, edges };
}

// ─── Step 4: Data Flow Graph ───

export function buildFieldGraph(model: DetailedRequirementsArtifact): { nodes: Node[]; edges: Edge[] } {
  const nodes: Node[] = [];
  const edges: Edge[] = [];

  // Fact table center
  if (model.fact_table) {
    nodes.push({
      id: "fact",
      type: "entityNode",
      position: { x: 300, y: 180 },
      data: {
        label: model.fact_table.table_name,
        role: "FACT",
        description: `Grain: ${model.fact_table.grain}`,
        attributes: model.fact_table.fields.slice(0, 4).map((f) => f.target_field),
        color: ENTITY_COLORS.FACT,
      },
    });
  }

  // Dimension tables around the fact
  const dims = model.dimension_tables || [];
  const angleStep = (2 * Math.PI) / Math.max(dims.length, 1);
  const radius = 220;

  dims.forEach((dim, i) => {
    const angle = angleStep * i - Math.PI / 2;
    nodes.push({
      id: `dim-${i}`,
      type: "entityNode",
      position: {
        x: 300 + radius * Math.cos(angle),
        y: 200 + radius * Math.sin(angle),
      },
      data: {
        label: dim.table_name,
        role: "DIM",
        description: `${dim.fields.length} fields`,
        attributes: dim.fields.slice(0, 3).map((f) => f.target_field),
        color: ENTITY_COLORS.DIM,
      },
    });

    edges.push({
      id: `e-fact-dim-${i}`,
      source: "fact",
      target: `dim-${i}`,
      style: { stroke: "#3DDBB8", strokeWidth: 2 },
    });
  });

  return { nodes, edges };
}
