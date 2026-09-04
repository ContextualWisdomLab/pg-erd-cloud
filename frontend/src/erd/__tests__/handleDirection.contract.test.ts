import type { Edge, Node } from '@xyflow/react';
import { describe, expect, it } from 'vitest';

import type { TableNodeData } from '../convert';
import { exportDDL } from '../export';
import { exportDictionaryCsv } from '../exportDataDictionary';
import { sourceColumnHandleId, targetColumnHandleId } from '../handleUtils';

const nodes: Node<TableNodeData>[] = [
  {
    id: 'source',
    type: 'tableNode',
    position: { x: 0, y: 0 },
    data: {
      title: 'source_table',
      badges: { pk: false, fk: true },
      columns: [
        { column_name: 'account_id', data_type: 'integer', is_pk: false, is_not_null: false },
        { column_name: 'alternate_id', data_type: 'integer', is_pk: false, is_not_null: false },
      ],
    },
  },
  {
    id: 'target',
    type: 'tableNode',
    position: { x: 0, y: 0 },
    data: {
      title: 'target_table',
      badges: { pk: true, fk: false },
      columns: [
        { column_name: 'id', data_type: 'integer', is_pk: true, is_not_null: true },
      ],
    },
  },
];

const swappedDirectionEdge: Edge = {
  id: 'fk_swapped_direction',
  source: 'source',
  target: 'target',
  sourceHandle: targetColumnHandleId('account_id'),
  targetHandle: sourceColumnHandleId('id'),
  data: {},
};

describe('column-handle direction contract', () => {
  it('does not treat target/source-prefixed handles as a valid DDL relationship', () => {
    const ddl = exportDDL(nodes, [swappedDirectionEdge]);

    expect(ddl).toContain('FOREIGN KEY (/* source columns */)');
    expect(ddl).toContain('REFERENCES "target_table" (/* target columns */)');
    expect(ddl).not.toContain('FOREIGN KEY ("account_id")');
  });

  it('does not mark a target-prefixed source handle as a dictionary FK column', () => {
    const csv = exportDictionaryCsv(nodes, [swappedDirectionEdge]);

    expect(csv).toContain('"source_table","","account_id","integer","N","N","N","",""');
  });
});
