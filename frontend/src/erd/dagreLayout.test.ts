import { describe, it, expect } from 'vitest';
import { computeDagreLayout } from './dagreLayout';
import type { Node, Edge } from '@xyflow/react';
import type { TableNodeData } from './convert';

describe('dagreLayout', () => {
  it('should layout nodes using dagre', () => {
    const nodes: Node<TableNodeData>[] = [
      {
        id: '1',
        type: 'tableNode',
        position: { x: 0, y: 0 },
        data: { title: 'users', columns: [], badges: { pk: false, fk: false } },
      },
      {
        id: '2',
        type: 'tableNode',
        position: { x: 0, y: 0 },
        data: { title: 'posts', columns: [], badges: { pk: false, fk: false } },
      }
    ];
    const edges: Edge[] = [
      { id: 'e1-2', source: '1', target: '2' }
    ];

    const result = computeDagreLayout(nodes, edges);
    expect(result.length).toBe(2);
    expect(result[0].position.x).not.toBeNull();
    expect(result[0].position.y).not.toBeNull();
  });
});
