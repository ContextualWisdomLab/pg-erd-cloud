import type { Edge, Node } from '@xyflow/react';
import { describe, expect, it } from 'vitest';
import type { TableNodeData } from '../convert';
import { exportPrisma } from '../prisma';

const nodes: Node<TableNodeData>[] = [
  {
    id: 'orders',
    position: { x: 0, y: 0 },
    data: {
      title: 'orders',
      badges: { pk: true, fk: true },
      columns: [
        { column_name: 'id', data_type: 'serial', is_pk: true, is_not_null: true },
        { column_name: 'account_id', data_type: 'integer', is_pk: false, is_not_null: true },
      ],
    },
  },
  {
    id: 'accounts',
    position: { x: 100, y: 0 },
    data: {
      title: 'accounts',
      badges: { pk: true, fk: false },
      columns: [{ column_name: 'id', data_type: 'serial', is_pk: true, is_not_null: true }],
    },
  },
];

describe('Prisma exporter branch completeness', () => {
  it('uses the default relation name when a valid edge has an empty label', () => {
    const edges: Edge[] = [
      {
        id: 'orders-accounts',
        source: 'orders',
        target: 'accounts',
        sourceHandle: 'src-account_id',
        targetHandle: 'tgt-id',
        label: '',
      },
    ];

    const schema = exportPrisma(nodes, edges);

    expect(schema).toContain('@relation("orders_accounts"');
    expect(schema).toContain('model orders');
    expect(schema).toContain('model accounts');
  });

  it('falls back safely when prefixed handles contain no field identifier', () => {
    const edges: Edge[] = [
      {
        id: 'empty-handles',
        source: 'orders',
        target: 'accounts',
        sourceHandle: 'src-',
        targetHandle: 'tgt-',
      },
    ];

    expect(() => exportPrisma(nodes, edges)).not.toThrow();
  });

  it('ignores a non-empty source handle that does not use the src prefix', () => {
    const edges: Edge[] = [
      {
        id: 'malformed-source-handle',
        source: 'orders',
        target: 'accounts',
        sourceHandle: 'account_id',
        targetHandle: 'tgt-id',
      },
    ];

    const schema = exportPrisma(nodes, edges);

    expect(schema).not.toContain('@relation("orders_accounts"');
    expect(schema).toContain('model orders');
  });
});
