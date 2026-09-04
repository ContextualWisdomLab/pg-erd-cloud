import type { Edge, Node } from '@xyflow/react';
import { describe, expect, it } from 'vitest';
import type { TableNodeData } from '../convert';
import { exportDDL } from '../export';
import { parseColumnNameFromHandle } from '../handleUtils';
import { exportPrisma } from '../prisma';

const nodes: Node<TableNodeData>[] = [
  {
    id: 'users',
    position: { x: 0, y: 0 },
    data: {
      title: 'users',
      badges: { pk: true, fk: false },
      columns: [
        { column_name: 'id', data_type: 'serial', is_pk: true, is_not_null: true },
      ],
    },
  },
  {
    id: 'posts',
    position: { x: 100, y: 0 },
    data: {
      title: 'posts',
      badges: { pk: true, fk: true },
      columns: [
        { column_name: 'id', data_type: 'serial', is_pk: true, is_not_null: true },
        { column_name: 'user_id', data_type: 'integer', is_pk: false, is_not_null: true },
        { column_name: 'author_id', data_type: 'integer', is_pk: false, is_not_null: true },
      ],
    },
  },
];

function relationEdge(sourceHandle: string, targetHandle: string): Edge {
  return {
    id: 'posts-users',
    source: 'posts',
    target: 'users',
    sourceHandle,
    targetHandle,
    label: 'posts_users',
  };
}

describe('ERD handle resolution', () => {
  it('keeps persisted legacy raw handles export-compatible', () => {
    const edge = relationEdge('src-user_id', 'tgt-id');
    const prisma = exportPrisma(nodes, [edge]);
    const ddl = exportDDL(nodes, [edge]);

    expect(prisma).toContain(
      'users_user_id users @relation("posts_users", fields: [user_id], references: [id])',
    );
    expect(ddl).toContain('FOREIGN KEY ("user_id")');
    expect(ddl).toContain('REFERENCES "users" ("id")');
  });

  it('keeps canonical hex handles export-compatible', () => {
    const edge = relationEdge(
      'src-c-0075-0073-0065-0072-005f-0069-0064',
      'tgt-c-0069-0064',
    );
    const prisma = exportPrisma(nodes, [edge]);
    const ddl = exportDDL(nodes, [edge]);

    expect(prisma).toContain(
      'users_user_id users @relation("posts_users", fields: [user_id], references: [id])',
    );
    expect(ddl).toContain('FOREIGN KEY ("user_id")');
    expect(ddl).toContain('REFERENCES "users" ("id")');
  });

  it('fails closed for malformed canonical handle payloads', () => {
    expect(() => parseColumnNameFromHandle('c-zzzz')).not.toThrow();
    expect(parseColumnNameFromHandle('c-zzzz')).toBe('');
    expect(parseColumnNameFromHandle('c-110000')).toBe('');
  });
});
