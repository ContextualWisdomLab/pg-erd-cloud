import { afterEach, describe, expect, it } from 'vitest';
import type { Edge, Node } from '@xyflow/react';

import type { TableNodeData } from '../convert';
import { exportPrisma } from '../prisma';

const originalArrayIncludes = Array.prototype.includes;

afterEach(() => {
  Array.prototype.includes = originalArrayIncludes;
});

function relationFixture(relationCount: number): {
  nodes: Node<TableNodeData>[];
  edges: Edge[];
} {
  const source: Node<TableNodeData> = {
    id: 'source',
    position: { x: 0, y: 0 },
    data: {
      title: 'orders',
      badges: { pk: true, fk: true },
      columns: [
        { column_name: 'id', data_type: 'serial', is_pk: true, is_not_null: true },
        ...Array.from({ length: relationCount }, (_, index) => ({
          column_name: `fk_${index}`,
          data_type: 'integer',
          is_pk: false,
          is_not_null: true,
        })),
      ],
    },
  };

  const targets: Node<TableNodeData>[] = Array.from({ length: relationCount }, (_, index) => ({
    id: `target-${index}`,
    position: { x: index * 10, y: 100 },
    data: {
      title: `target_${index}`,
      badges: { pk: true, fk: false },
      columns: [
        { column_name: 'id', data_type: 'serial', is_pk: true, is_not_null: true },
      ],
    },
  }));

  const edges: Edge[] = targets.map((target, index) => ({
    id: `edge-${index}`,
    source: source.id,
    target: target.id,
    sourceHandle: `src-fk_${index}`,
    targetHandle: 'tgt-id',
    label: `orders_target_${index}`,
  }));

  return { nodes: [source, ...targets], edges };
}

describe('exportPrisma relation lookup', () => {
  it('does not scan every source-model relation for every exported column', () => {
    const relationCount = 32;
    const { nodes, edges } = relationFixture(relationCount);
    let sourceFieldArrayScans = 0;

    Array.prototype.includes = function includes(
      this: unknown[],
      searchElement: unknown,
      fromIndex?: number,
    ): boolean {
      if (
        this.length === 1 &&
        typeof this[0] === 'string' &&
        /^fk_\d+$/.test(this[0]) &&
        typeof searchElement === 'string'
      ) {
        sourceFieldArrayScans += 1;
      }
      return originalArrayIncludes.call(this, searchElement, fromIndex);
    };

    const output = exportPrisma(nodes, edges);

    expect(output).toContain('target_31_fk_31 target_31');
    // One bounded pass per relation is acceptable; C×E relation scans are not.
    expect(sourceFieldArrayScans).toBeLessThanOrEqual(relationCount);
  });

  it('preserves the existing last-edge-wins relation choice for duplicate source fields', () => {
    const source: Node<TableNodeData> = {
      id: 'source',
      position: { x: 0, y: 0 },
      data: {
        title: 'orders',
        badges: { pk: true, fk: true },
        columns: [
          { column_name: 'id', data_type: 'serial', is_pk: true, is_not_null: true },
          { column_name: 'customer_id', data_type: 'integer', is_pk: false, is_not_null: true },
        ],
      },
    };
    const targetA: Node<TableNodeData> = {
      id: 'target-a',
      position: { x: 100, y: 0 },
      data: {
        title: 'customers_a',
        badges: { pk: true, fk: false },
        columns: [{ column_name: 'id', data_type: 'serial', is_pk: true, is_not_null: true }],
      },
    };
    const targetB: Node<TableNodeData> = {
      id: 'target-b',
      position: { x: 200, y: 0 },
      data: {
        title: 'customers_b',
        badges: { pk: true, fk: false },
        columns: [{ column_name: 'id', data_type: 'serial', is_pk: true, is_not_null: true }],
      },
    };
    const edges: Edge[] = [
      {
        id: 'edge-a',
        source: source.id,
        target: targetA.id,
        sourceHandle: 'src-customer_id',
        targetHandle: 'tgt-id',
        label: 'orders_customer_a',
      },
      {
        id: 'edge-b',
        source: source.id,
        target: targetB.id,
        sourceHandle: 'src-customer_id',
        targetHandle: 'tgt-id',
        label: 'orders_customer_b',
      },
    ];

    const output = exportPrisma([source, targetA, targetB], edges);

    expect(output).toContain(
      'customers_b_customer_id customers_b @relation("orders_customer_b", fields: [customer_id], references: [id])',
    );
    expect(output).not.toContain(
      'customers_a_customer_id customers_a @relation("orders_customer_a", fields: [customer_id], references: [id])',
    );
  });
});
