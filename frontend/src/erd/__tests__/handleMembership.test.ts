import { describe, expect, it } from 'vitest';
import type { Edge, Node } from '@xyflow/react';

import type { TableNodeData } from '../convert';
import { exportDDL } from '../export';
import { sourceColumnHandleId, targetColumnHandleId } from '../handleUtils';
import { exportPrisma } from '../prisma';

function relationFixture(): { parent: Node<TableNodeData>; child: Node<TableNodeData>; staleEdge: Edge } {
  const parent: Node<TableNodeData> = {
    id: 'parent',
    type: 'tableNode',
    position: { x: 0, y: 0 },
    data: {
      title: 'public.users',
      columns: [
        { column_name: 'id', data_type: 'integer', is_not_null: true, is_pk: true },
      ],
      badges: { pk: true, fk: false },
    },
  };
  const child: Node<TableNodeData> = {
    id: 'child',
    type: 'tableNode',
    position: { x: 0, y: 0 },
    data: {
      title: 'public.posts',
      columns: [
        { column_name: 'user_id', data_type: 'integer', is_not_null: true, is_pk: false },
      ],
      badges: { pk: false, fk: true },
    },
  };
  const staleEdge: Edge = {
    id: 'fk-stale',
    source: child.id,
    target: parent.id,
    sourceHandle: sourceColumnHandleId('ghost_user_id'),
    targetHandle: targetColumnHandleId('ghost_id'),
    label: 'fk_posts_users',
  };
  return { parent, child, staleEdge };
}

describe('ERD edge handle membership', () => {
  it('does not trust a decodable handle for a column absent from its endpoint node in DDL export', () => {
    const { parent, child, staleEdge } = relationFixture();

    const ddl = exportDDL([parent, child], [staleEdge]);

    expect(ddl).not.toContain('ghost_user_id');
    expect(ddl).not.toContain('ghost_id');
    expect(ddl).toContain('FOREIGN KEY ("user_id")');
    expect(ddl).toContain('REFERENCES "public.users" ("id")');
  });

  it('does not create a Prisma relation from a decodable handle absent from its endpoint node', () => {
    const { parent, child, staleEdge } = relationFixture();

    const schema = exportPrisma([parent, child], [staleEdge]);

    expect(schema).not.toContain('ghost_user_id');
    expect(schema).not.toContain('ghost_id');
    expect(schema).not.toContain('@relation("fk_posts_users"');
  });
});
