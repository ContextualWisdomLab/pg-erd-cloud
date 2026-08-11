import { describe, it, expect } from 'vitest';
import { exportPrisma } from '../prisma';
import type { Node, Edge } from '@xyflow/react';
import type { TableNodeData } from '../convert';

describe('exportPrisma', () => {
  it('returns empty comment if no nodes', () => {
    const result = exportPrisma([], []);
    expect(result).toBe('// No tables to export\n');
  });

  it('exports simple model correctly', () => {
    const nodes: Node<TableNodeData>[] = [
      {
        id: '1',
        position: { x: 0, y: 0 },
        data: {
          title: 'users',
          badges: { pk: true, fk: false },
          columns: [
            { column_name: 'id', data_type: 'integer', is_pk: true, is_not_null: true },
            { column_name: 'name', data_type: 'varchar(255)', is_not_null: false, is_pk: false },
          ],
        },
      },
    ];

    const result = exportPrisma(nodes, []);
    expect(result).toContain('model users {');
    expect(result).toContain('id Int @id');
    expect(result).toContain('name String?');
  });

  it('handles foreign key relations correctly', () => {
    const nodes: Node<TableNodeData>[] = [
      {
        id: '1',
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
        id: '2',
        position: { x: 100, y: 100 },
        data: {
          title: 'posts',
          badges: { pk: true, fk: true },
          columns: [
            { column_name: 'id', data_type: 'serial', is_pk: true, is_not_null: true },
            { column_name: 'user_id', data_type: 'integer', is_not_null: true, is_pk: false },
          ],
        },
      },
    ];

    const edges: Edge[] = [
      {
        id: 'e1',
        source: '2',
        target: '1',
        sourceHandle: 'src-user_id',
        targetHandle: 'tgt-id',
        label: 'users_posts',
      },
    ];

    const result = exportPrisma(nodes, edges);

    // Check posts model
    expect(result).toContain('model posts {');
    expect(result).toContain('user_id Int');
    expect(result).toContain('users_user_id users @relation("users_posts", fields: [user_id], references: [id])');

    // Check users model (back-relation)
    expect(result).toContain('model users {');
    expect(result).toContain('posts_user_id posts[] @relation("users_posts")');
  });

  it('maps various types properly', () => {
    const nodes: Node<TableNodeData>[] = [
      {
        id: '1',
        position: { x: 0, y: 0 },
        data: {
          title: 'all_types',
          badges: { pk: true, fk: false },
          columns: [
            { column_name: 'c_uuid', data_type: 'uuid', is_pk: true, is_not_null: true },
            { column_name: 'c_bool', data_type: 'boolean', is_not_null: true, is_pk: false },
            { column_name: 'c_time', data_type: 'timestamp', is_not_null: true, is_pk: false },
            { column_name: 'c_float', data_type: 'numeric', is_not_null: true, is_pk: false },
            { column_name: 'c_json', data_type: 'jsonb', is_not_null: true, is_pk: false },
            { column_name: 'c_bytes', data_type: 'bytea', is_not_null: true, is_pk: false },
            { column_name: 'c_other', data_type: 'unknown', is_not_null: true, is_pk: false },
          ],
        },
      },
    ];

    const result = exportPrisma(nodes, []);
    expect(result).toContain('c_uuid String @id @default(uuid())');
    expect(result).toContain('c_bool Boolean');
    expect(result).toContain('c_time DateTime');
    expect(result).toContain('c_float Float');
    expect(result).toContain('c_json Json');
    expect(result).toContain('c_bytes Bytes');
    expect(result).toContain('c_other String');
  });

  it('handles unique constraints properly', () => {
    const nodes: Node<TableNodeData>[] = [
      {
        id: '1',
        position: { x: 0, y: 0 },
        data: {
          title: 'unique_test',
          badges: { pk: true, fk: false },
          columns: [
            { column_name: 'id', data_type: 'integer', is_pk: true, is_not_null: true },
            { column_name: 'email', data_type: 'text', is_not_null: true, is_pk: false },
          ],

        },
      },
    ];

    const result = exportPrisma(nodes, []);
    expect(result).toContain('email String @unique');
  });

  it('handles invalid prisma identifier names', () => {
    const nodes: Node<TableNodeData>[] = [
      {
        id: '1',
        position: { x: 0, y: 0 },
        data: {
          title: '123invalid',
          badges: { pk: true, fk: false },
          columns: [
            { column_name: '123col', data_type: 'integer', is_pk: true, is_not_null: true },
            { column_name: 'a b c', data_type: 'text', is_not_null: true, is_pk: false },
          ],
        },
      },
    ];

    const result = exportPrisma(nodes, []);
    expect(result).toContain('model M_123invalid');
    expect(result).toContain('M_123col Int @id');
    expect(result).toContain('a_b_c String');
  });

  it('handles edge cases for edges without handles or invalid ids', () => {
    const nodes: Node<TableNodeData>[] = [
      {
        id: '1',
        position: { x: 0, y: 0 },
        data: {
          title: 'A',
          badges: { pk: true, fk: true },
          columns: [
            { column_name: 'id', data_type: 'integer', is_pk: true, is_not_null: true },
          ],
        },
      },
      {
        id: '2',
        position: { x: 100, y: 100 },
        data: {
          title: 'B',
          badges: { pk: true, fk: false },
          columns: [
            { column_name: 'id', data_type: 'integer', is_pk: true, is_not_null: true },
          ],
        },
      },
    ];

    const edges: Edge[] = [
      { id: 'e1', source: 'invalid', target: '2' },
      { id: 'e2', source: '1', target: '2' },
    ];

    const result = exportPrisma(nodes, edges);
    expect(result).toContain('model A');
    expect(result).toContain('model B');
  });

  it('ignores non-source handles and renders singular back-relations for primary keys', () => {
    const nodes: Node<TableNodeData>[] = [
      {
        id: 'parent',
        position: { x: 0, y: 0 },
        data: {
          title: 'parents',
          badges: { pk: true, fk: false },
          columns: [
            { column_name: 'id', data_type: 'serial', is_pk: true, is_not_null: true },
          ],
        },
      },
      {
        id: 'child',
        position: { x: 100, y: 0 },
        data: {
          title: 'children',
          badges: { pk: true, fk: true },
          columns: [
            { column_name: 'id', data_type: 'integer', is_pk: true, is_not_null: true },
          ],
        },
      },
    ];

    const result = exportPrisma(nodes, [
      {
        id: 'ignored-handle',
        source: 'child',
        target: 'parent',
        sourceHandle: 'legacy-id',
        targetHandle: 'tgt-id',
      },
      {
        id: 'primary-key-relation',
        source: 'child',
        target: 'parent',
        sourceHandle: 'src-id',
        targetHandle: 'tgt-id',
        label: 'child_parent',
      },
    ]);

    expect(result).toContain('children_id children? @relation("child_parent")');
    expect(result).not.toContain('@relation("children_parents"');
  });

  it('handles missing is_not_null logic for optional relationships', () => {
    const nodes: Node<TableNodeData>[] = [
      {
        id: '1',
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
        id: '2',
        position: { x: 100, y: 100 },
        data: {
          title: 'profiles',
          badges: { pk: true, fk: true },
          columns: [
            { column_name: 'id', data_type: 'serial', is_pk: true, is_not_null: true },
            { column_name: 'user_id', data_type: 'integer', is_not_null: false, is_pk: false },
          ],

        },
      },
    ];

    const edges: Edge[] = [
      {
        id: 'e1',
        source: '2',
        target: '1',
        sourceHandle: 'src-user_id',
        targetHandle: 'tgt-id',
        label: '1to1',
      },
    ];

    const result = exportPrisma(nodes, edges);
    expect(result).toContain('users_user_id users? @relation("M_1to1", fields: [user_id], references: [id])');
    expect(result).toContain('profiles_user_id profiles[] @relation("M_1to1")');
  });
});
