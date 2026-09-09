import { describe, expect, it } from 'vitest';
import type { Edge, Node } from '@xyflow/react';

import type { TableNodeData } from '../convert';
import { exportDDL } from '../export';
import { exportDbml } from '../dbml';
import { parseHandleId, sourceColumnHandleId, targetColumnHandleId } from '../handleUtils';
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

  it('does not create a DBML relation from a decodable handle absent from its endpoint node', () => {
    const { parent, child, staleEdge } = relationFixture();

    const dbml = exportDbml([parent, child], [staleEdge]);

    expect(dbml).not.toContain('ghost_user_id');
    expect(dbml).not.toContain('ghost_id');
    expect(dbml).not.toContain('Ref:');
  });

  it('does not create a Prisma relation from a decodable handle absent from its endpoint node', () => {
    const { parent, child, staleEdge } = relationFixture();

    const schema = exportPrisma([parent, child], [staleEdge]);

    expect(schema).not.toContain('ghost_user_id');
    expect(schema).not.toContain('ghost_id');
    expect(schema).not.toContain('@relation("fk_posts_users"');
  });
});


describe('canonical ERD handle decoding', () => {
  it('round-trips empty, Unicode, and non-BMP column names', () => {
    for (const columnName of ['', '사용자_識別子', 'emoji_😀']) {
      expect(parseHandleId(sourceColumnHandleId(columnName), 'src-')).toBe(columnName);
      expect(parseHandleId(targetColumnHandleId(columnName), 'tgt-')).toBe(columnName);
    }
  });

  it('rejects partial, aliased, out-of-range, and wrong-prefix encodings', () => {
    expect(parseHandleId('src-c-0061junk', 'src-')).toBeNull();
    expect(parseHandleId('src-c-00AF', 'src-')).toBeNull();
    expect(parseHandleId('src-c-000061', 'src-')).toBeNull();
    expect(parseHandleId('src-c-110000', 'src-')).toBeNull();
    expect(parseHandleId(sourceColumnHandleId('id'), 'tgt-')).toBeNull();
  });
});
