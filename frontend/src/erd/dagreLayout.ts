import * as dagre from '@dagrejs/dagre';
import type { Node, Edge } from '@xyflow/react';
import type { TableNodeData } from './convert';

export function computeDagreLayout(
  nodes: Node<TableNodeData>[],
  edges: Edge[],
  direction: 'TB' | 'LR' = 'LR'
): Node<TableNodeData>[] {
  const dagreGraph = new dagre.graphlib.Graph();
  dagreGraph.setDefaultEdgeLabel(() => ({}));

  // dagre에 방향 설정 (기본은 LR: 좌에서 우로)
  dagreGraph.setGraph({ rankdir: direction, align: 'UL', ranksep: 120, nodesep: 60 });

  nodes.forEach((node) => {
    // ERD node의 대략적인 크기 설정 (고정 크기이거나 컬럼 수에 따라 높이를 다르게 줄 수 있음)
    // TableNode.tsx에서 MAX_RENDERED_COLUMNS (25) 등으로 처리되지만 평균적인 높이를 할당
    const nodeWidth = 280;
    const headerHeight = 40;
    const rowHeight = 25;
    const columnCount = Math.min(node.data.columns?.length || 0, 25);
    const nodeHeight = headerHeight + (columnCount * rowHeight) + 40;

    dagreGraph.setNode(node.id, { width: nodeWidth, height: nodeHeight });
  });

  edges.forEach((edge) => {
    // Only add edges for nodes that actually exist in the graph.
    // Dagre will auto-create missing nodes with undefined sizes and mess up coordinates
    // if edges reference non-existent nodes (like disconnected handles).
    if (dagreGraph.hasNode(edge.source) && dagreGraph.hasNode(edge.target)) {
      dagreGraph.setEdge(edge.source, edge.target);
    }
  });

  try {
    dagre.layout(dagreGraph);
  } catch (error) {
    console.error('Dagre layout failed:', error);
    return nodes.map((node) => ({ ...node }));
  }

  return nodes.map((node) => {
    const nodeWithPosition = dagreGraph.node(node.id);

    // When dagre fails, it may not throw, but instead drops x/y values
    // for disconnected nodes or completely unassigned geometry.
    // Also dagre drops x/y values when edges are completely unresolvable.
    const validGeometry =
      nodeWithPosition &&
      nodeWithPosition.x !== undefined &&
      nodeWithPosition.y !== undefined &&
      Number.isFinite(nodeWithPosition.x) &&
      Number.isFinite(nodeWithPosition.y) &&
      Number.isFinite(nodeWithPosition.width) &&
      Number.isFinite(nodeWithPosition.height);

    if (!validGeometry) {
      return { ...node, position: { ...node.position } };
    }

    return {
      ...node,
      position: {
        x: nodeWithPosition.x - nodeWithPosition.width / 2,
        y: nodeWithPosition.y - nodeWithPosition.height / 2,
      },
    };
  });
}
