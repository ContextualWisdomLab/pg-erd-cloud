import dagre from "dagre";
import type { Node, Edge } from "@xyflow/react";
import type { TableNodeData } from "./convert";

const nodeWidth = 320;
const nodeHeight = 220; // Estimated height, should ideally vary based on columns, but this is a reasonable default

export function computeDagreLayout(
  nodes: Node<TableNodeData>[],
  edges: Edge[],
  direction: "TB" | "LR" = "LR"
): Node<TableNodeData>[] {
  const dagreGraph = new dagre.graphlib.Graph();
  dagreGraph.setDefaultEdgeLabel(() => ({}));

  dagreGraph.setGraph({ rankdir: direction });

  nodes.forEach((node) => {
    // A slightly more accurate height estimation could be:
    // base height (e.g. 50 for header) + num_columns * row_height (e.g. 24)
    const height = Math.max(nodeHeight, 50 + (node.data.columns.length * 24));
    dagreGraph.setNode(node.id, { width: nodeWidth, height: height });
  });

  edges.forEach((edge) => {
    dagreGraph.setEdge(edge.source, edge.target);
  });

  dagre.layout(dagreGraph);

  return nodes.map((node) => {
    const nodeWithPosition = dagreGraph.node(node.id);
    return {
      ...node,
      position: {
        x: nodeWithPosition.x - nodeWidth / 2,
        y: nodeWithPosition.y - nodeWithPosition.height / 2,
      },
    };
  });
}
