import dagre from 'dagre';
import { type Node, type Edge } from '@xyflow/react';
import type { TableNodeData } from './convert';
import { GRID_X_GAP, GRID_Y_GAP } from './layoutConstants';

export function computeDagreLayout(
  nodes: Node<TableNodeData>[],
  edges: Edge[]
): Node<TableNodeData>[] {
  const dagreGraph = new dagre.graphlib.Graph();
  dagreGraph.setDefaultEdgeLabel(() => ({}));

  dagreGraph.setGraph({
    rankdir: 'LR',
    nodesep: 80,
    ranksep: 200,
  });

  nodes.forEach((node) => {
    // Estimating node dimensions. You can adjust this or pass actual dimensions if available
    const width = GRID_X_GAP - 40; // Approx 280
    const height = GRID_Y_GAP - 40; // Approx 180
    dagreGraph.setNode(node.id, { width, height });
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
        x: nodeWithPosition.x - nodeWithPosition.width / 2,
        y: nodeWithPosition.y - nodeWithPosition.height / 2,
      },
    };
  });
}
