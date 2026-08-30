import { describe, expect, it } from 'vitest';
import type { Edge, Node } from '@xyflow/react';
import type { TableNodeData } from '../convert';
import { sourceColumnHandleId, targetColumnHandleId } from '../handleUtils';
import { exportPrisma } from '../prisma';

function relationNodes(): Node<TableNodeData>[] {
  return [
    {
      id: 'orders',
      position: { x: 0, y: 0 },
      data: {
        title: 'orders',
        badges: { pk: true, fk: true },
        columns: [
          { column_name: 'id', data_type: 'serial', is_pk: true, is_not_null: true },
          { column_name: 'customer_id', data_type: 'integer', is_pk: false, is_not_null: true },
        ],
      },
    },
    {
      id: 'customers',
      position: { x: 100, y: 0 },
      data: {
        title: 'customers',
        badges: { pk: true, fk: false },
        columns: [
          { column_name: 'id', data_type: 'serial', is_pk: true, is_not_null: true },
        ],
      },
    },
  ];
}

function relationEdge(id: string, label: string): Edge {
  return {
    id,
    source: 'orders',
    target: 'customers',
    sourceHandle: sourceColumnHandleId('customer_id'),
    targetHandle: targetColumnHandleId('id'),
    label,
  };
}

describe('Prisma relation indexing', () => {
  it('fails closed when one scalar field is assigned multiple Prisma relations', () => {
    expect(() =>
      exportPrisma(relationNodes(), [
        relationEdge('edge-primary', 'orders_customer_primary'),
        relationEdge('edge-secondary', 'orders_customer_secondary'),
      ]),
    ).toThrowError(
      'Prisma export cannot represent multiple relations from orders.customer_id. Remove duplicate relation edges or use separate foreign-key columns.',
    );
  });

  it('does not rescan a source column array for every relation edge', () => {
    const nodes = relationNodes();
    const sourceColumns = nodes[0].data.columns;

    Object.defineProperty(sourceColumns, 'find', {
      configurable: true,
      value: () => {
        throw new Error('relation indexing must not call columns.find');
      },
    });

    const schema = exportPrisma(nodes, [
      relationEdge('edge-primary', 'orders_customer_primary'),
    ]);

    expect(schema).toContain(
      'customers_customer_id customers @relation("orders_customer_primary", fields: [customer_id], references: [id])',
    );
  });
});
