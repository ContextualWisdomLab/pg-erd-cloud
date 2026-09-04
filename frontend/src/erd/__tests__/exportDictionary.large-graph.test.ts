import { describe, it, expect } from 'vitest';
import { exportDictionaryCsv } from '../exportDataDictionary';
import { sourceColumnHandleId, targetColumnHandleId } from '../handleUtils';
import type { Node, Edge } from '@xyflow/react';
import type { TableNodeData } from '../convert';

describe('Export Dictionary large-graph contract', () => {
  it('preserves table and foreign-key columns across a 500-table synthetic graph', () => {
    const nodes: Node<TableNodeData>[] = [];
    const edges: Edge[] = [];
    const numTables = 500;
    const numCols = 20;

    for (let i = 0; i < numTables; i++) {
      nodes.push({
        id: `t${i}`,
        data: {
          title: `table_${i}`,
          columns: Array.from({ length: numCols }, (_, c) => ({
            column_name: `col_${c}`,
            data_type: 'text',
            is_not_null: false,
            is_pk: c === 0,
          })),
          badges: { pk: true, fk: i > 0 },
        },
        position: { x: 0, y: 0 },
      });

      if (i > 0) {
        edges.push({
          id: `e${i}`,
          source: `t${i}`,
          target: `t${i - 1}`,
          sourceHandle: sourceColumnHandleId('col_1'),
          targetHandle: targetColumnHandleId('col_0'),
          data: {},
        });
      }
    }

    const csv = exportDictionaryCsv(nodes, edges);

    expect(csv).toContain('table_0');
    expect(csv).toContain('table_499');
    expect(csv).toContain('col_0');
    expect(csv).toContain('col_1');
  });
});
