import dagre from 'dagre';
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
    dagreGraph.setEdge(edge.source, edge.target);
  });

  dagre.layout(dagreGraph);

  return nodes.map((node) => {
    const nodeWithPosition = dagreGraph.node(node.id);
    return {
      ...node,
      position: {
        // dagre가 계산한 x, y 좌표는 노드의 중심 좌표이므로 좌상단 좌표로 변환
        x: nodeWithPosition.x - nodeWithPosition.width / 2,
        y: nodeWithPosition.y - nodeWithPosition.height / 2,
      },
    };
  });
}
