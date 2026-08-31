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

function column(columnName: string, isPk = false) {
  return {
    column_name: columnName,
    data_type: isPk ? 'serial' : 'integer',
    is_pk: isPk,
    is_not_null: true,
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

  it.each([
    ['encoded column first', ['a', 'c-0061']],
    ['legacy raw column first', ['c-0061', 'a']],
  ])('fails closed on ambiguous source handles regardless of column order: %s', (_label, names) => {
    const nodes: Node<TableNodeData>[] = [
      {
        id: 'orders',
        position: { x: 0, y: 0 },
        data: {
          title: 'orders',
          badges: { pk: true, fk: true },
          columns: [column('id', true), ...names.map((name) => column(name))],
        },
      },
      {
        id: 'customers',
        position: { x: 100, y: 0 },
        data: {
          title: 'customers',
          badges: { pk: true, fk: false },
          columns: [column('id', true)],
        },
      },
    ];

    expect(() =>
      exportPrisma(nodes, [
        {
          id: 'edge-ambiguous-source',
          source: 'orders',
          target: 'customers',
          sourceHandle: sourceColumnHandleId('a'),
          targetHandle: targetColumnHandleId('id'),
          label: 'orders_customer',
        },
      ]),
    ).toThrowError(
      'Prisma export cannot resolve ambiguous source column handle orders.c-0061. Rename the colliding column or reconnect the relation.',
    );
  });

  it.each([
    ['encoded column first', ['a', 'c-0061']],
    ['legacy raw column first', ['c-0061', 'a']],
  ])('fails closed on ambiguous target handles regardless of column order: %s', (_label, names) => {
    const nodes: Node<TableNodeData>[] = [
      {
        id: 'orders',
        position: { x: 0, y: 0 },
        data: {
          title: 'orders',
          badges: { pk: true, fk: true },
          columns: [column('id', true), column('customer_id')],
        },
      },
      {
        id: 'customers',
        position: { x: 100, y: 0 },
        data: {
          title: 'customers',
          badges: { pk: false, fk: false },
          columns: names.map((name) => column(name)),
        },
      },
    ];

    expect(() =>
      exportPrisma(nodes, [
        {
          id: 'edge-ambiguous-target',
          source: 'orders',
          target: 'customers',
          sourceHandle: sourceColumnHandleId('customer_id'),
          targetHandle: targetColumnHandleId('a'),
          label: 'orders_customer',
        },
      ]),
    ).toThrowError(
      'Prisma export cannot resolve ambiguous target column handle customers.c-0061. Rename the colliding column or reconnect the relation.',
    );
  });

  it.each([
    ['colliding node first', false],
    ['legacy source first', true],
  ])('keeps node ids and legacy raw handles in separate namespaces: %s', (_label, reverseNodes) => {
    const legacySource: Node<TableNodeData> = {
      id: 'orders:west',
      position: { x: 0, y: 0 },
      data: {
        title: 'orders_west',
        badges: { pk: false, fk: true },
        columns: [column('customer:id')],
      },
    };
    const collidingNode: Node<TableNodeData> = {
      id: 'orders',
      position: { x: 50, y: 0 },
      data: {
        title: 'orders_other',
        badges: { pk: false, fk: false },
        columns: [column('west:customer:id')],
      },
    };
    const target: Node<TableNodeData> = {
      id: 'customers',
      position: { x: 100, y: 0 },
      data: {
        title: 'customers',
        badges: { pk: true, fk: false },
        columns: [column('id', true)],
      },
    };
    const sources = reverseNodes ? [collidingNode, legacySource] : [legacySource, collidingNode];

    const schema = exportPrisma([...sources, target], [
      {
        id: 'edge-legacy-raw-colon',
        source: 'orders:west',
        target: 'customers',
        sourceHandle: 'src-customer:id',
        targetHandle: targetColumnHandleId('id'),
        label: 'orders_customer',
      },
    ]);

    expect(schema).toContain(
      'customers_customer_id customers @relation("orders_customer", fields: [customer_id], references: [id])',
    );
  });
});
