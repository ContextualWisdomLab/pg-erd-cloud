import { describe, it, expect } from 'vitest';
import { computeDagreLayout } from './autoLayout';
import type { Node, Edge } from '@xyflow/react';
import type { TableNodeData } from './convert';

describe('computeDagreLayout', () => {
  it('should layout nodes correctly', () => {
    const nodes: Node<TableNodeData>[] = [
      { id: '1', data: { title: 'Table1', columns: [], badges: { pk: false, fk: false } }, position: { x: 0, y: 0 } },
      { id: '2', data: { title: 'Table2', columns: [], badges: { pk: false, fk: false } }, position: { x: 0, y: 0 } },
    ];
    const edges: Edge[] = [
      { id: 'e1-2', source: '1', target: '2' },
    ];

    const layoutedNodes = computeDagreLayout(nodes, edges);

    expect(layoutedNodes).toHaveLength(2);
    // Dagre will arrange them in LR, so node 2 should be to the right of node 1
    expect(layoutedNodes[1].position.x).toBeGreaterThan(layoutedNodes[0].position.x);
  });
});
