import { describe, it, expect } from 'vitest';
import { exportDictionaryCsv } from '../exportDataDictionary';
import { sourceColumnHandleId, targetColumnHandleId } from '../handleUtils';
import type { Node, Edge } from '@xyflow/react';
import type { TableNodeData } from '../convert';

describe('Export Dictionary Benchmark', () => {
  it('should efficiently export dictionaries for large graphs without N^2 scaling', () => {
    const nodes: Node<TableNodeData>[] = [];
    const edges: Edge[] = [];

    // Generate 500 tables, each with 20 columns
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
          badges: { pk: true, fk: i > 0 }
        },
        position: { x: 0, y: 0 }
      });

      // Connect each table to the previous one
      if (i > 0) {
        edges.push({
          id: `e${i}`,
          source: `t${i}`,
          target: `t${i-1}`,
          sourceHandle: sourceColumnHandleId('col_1'), // FK column
          targetHandle: targetColumnHandleId('col_0'), // PK column
          data: {}
        });
      }
    }

    const start = performance.now();
    const csv = exportDictionaryCsv(nodes, edges);
    const elapsed = performance.now() - start;

    expect(csv).toContain('table_0');
    expect(csv).toContain('table_499');

    // This previously took hundreds of milliseconds due to O(N * C * E)
    // and is now expected to be well under 50ms.
    console.log(`Large CSV export took: ${elapsed.toFixed(2)}ms`);
    expect(elapsed).toBeLessThan(100);
  });
});
