import { describe, expect, it } from 'vitest';

import type { Node } from '@xyflow/react';
import type { TableNodeData } from '../convert';
import { exportDictionaryCsv } from '../exportDataDictionary';

describe('exportDataDictionary CSV Injection Protection', () => {
  it('neutralizes fullwidth equals signs (=) in CSV export', () => {
    const nodes: Node<TableNodeData>[] = [
      {
        id: 'table1',
        type: 'table',
        position: { x: 0, y: 0 },
        data: {
          title: 'table1',
          badges: { pk: false, fk: false },
          columns: [{ column_name: 'col1', data_type: 'text', column_comment: '\uFF1D1+2', is_pk: false, is_not_null: false }],
        },
      },
    ];
    const csv = exportDictionaryCsv(nodes, []);
    expect(csv).toContain('\'\uFF1D1+2');
  });

  it('neutralizes fullwidth equals signs (=) in default exportDataDictionary behavior', () => {
    const nodes: Node<TableNodeData>[] = [
      {
        id: 'table2',
        type: 'table',
        position: { x: 0, y: 0 },
        data: {
          title: 'table2',
          badges: { pk: false, fk: false },
          columns: [{ column_name: 'col2', data_type: 'text', column_comment: '\uFF1D1+2', is_pk: false, is_not_null: false }],
        },
      },
    ];
    const csv = exportDictionaryCsv(nodes, []);
    expect(csv).toContain('\'\uFF1D1+2');
  });
});
