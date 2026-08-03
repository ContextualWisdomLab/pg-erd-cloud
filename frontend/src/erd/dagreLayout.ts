import * as dagre from '@dagrejs/dagre';
import type { Edge, Node } from '@xyflow/react';
import type { TableNodeData } from './convert';

/**
 * Compute a deterministic relationship-aware layout without mutating the input graph.
 *
 * If Dagre cannot produce complete finite geometry, the affected node keeps its
 * existing position so a layout failure never collapses the ERD onto the origin.
 */
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
    dagreGraph.setEdge(edge.source, edge.target);
  });

  try {
    dagre.layout(dagreGraph);
  } catch {
    return nodes.map((node) => ({
      ...node,
      position: { ...node.position },
    }));
  }

  return nodes.map((node) => {
    const nodeWithPosition = dagreGraph.node(node.id);
    const x = nodeWithPosition?.x;
    const y = nodeWithPosition?.y;
    const width = nodeWithPosition?.width;
    const height = nodeWithPosition?.height;

    if (
      typeof x !== 'number' ||
      typeof y !== 'number' ||
      typeof width !== 'number' ||
      typeof height !== 'number' ||
      !Number.isFinite(x) ||
      !Number.isFinite(y) ||
      !Number.isFinite(width) ||
      !Number.isFinite(height)
    ) {
      return {
        ...node,
        position: { ...node.position },
      };
    }

    return {
      ...node,
      position: {
        x: x - width / 2,
        y: y - height / 2,
      },
    };
  });
}
