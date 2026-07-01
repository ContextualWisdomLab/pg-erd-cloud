import dagre from "dagre";
import type { Node, Edge } from "@xyflow/react";

const NODE_WIDTH = 320;
const NODE_HEIGHT = 220; // This is an estimated average height since tables vary by column count

/**
 * Computes a hierarchical (DAG) layout using Dagre, taking relations (edges) into account.
 */
export function computeDagreLayout<T extends Record<string, any>>(
  nodes: Node<T>[],
  edges: Edge[],
  direction: "TB" | "LR" = "LR",
): Node<T>[] {
  if (nodes.length === 0) return [];

  const dagreGraph = new dagre.graphlib.Graph();
  dagreGraph.setDefaultEdgeLabel(() => ({}));

  // Configure general graph options
  dagreGraph.setGraph({
    rankdir: direction,
    nodesep: 80,
    ranksep: 250, // Space between ranks (layers)
  });

  // Pre-calculate sets for fast lookups (O(1))
  const nodeMap = new Map(nodes.map((n) => [n.id, n]));

  // Add nodes to the dagre graph
  nodes.forEach((node) => {
    // We use a fixed size for the layout algorithm, but in reality React Flow
    // nodes vary in height based on columns. Using an average or fixed size
    // helps keep the layout predictable.
    dagreGraph.setNode(node.id, {
      width: node.measured?.width ?? NODE_WIDTH,
      height: node.measured?.height ?? NODE_HEIGHT,
    });
  });

  // Add edges to the dagre graph
  edges.forEach((edge) => {
    if (nodeMap.has(edge.source) && nodeMap.has(edge.target)) {
      dagreGraph.setEdge(edge.source, edge.target);
    }
  });

  // Run the layout algorithm
  dagre.layout(dagreGraph);

  // Return nodes with updated positions
  return nodes.map((node) => {
    const nodeWithPosition = dagreGraph.node(node.id);

    // dagre returns center coordinates, but React Flow expects top-left coordinates.
    const x = nodeWithPosition.x - (node.measured?.width ?? NODE_WIDTH) / 2;
    const y = nodeWithPosition.y - (node.measured?.height ?? NODE_HEIGHT) / 2;

    return {
      ...node,
      position: { x, y },
    };
  });
}
