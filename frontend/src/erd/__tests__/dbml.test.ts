import { describe, it, expect } from 'vitest';
import type { Node, Edge } from '@xyflow/react';
import { exportDbml } from '../dbml';
import type { TableNodeData } from '../convert';

describe('exportDbml', () => {
  it('should return empty string for empty nodes', () => {
    const result = exportDbml([], []);
    expect(result).toBe('');
  });

  it('should export simple table', () => {
    const nodes: Node<TableNodeData>[] = [
      {
        id: '1',
        type: 'tableNode',
        position: { x: 0, y: 0 },
        data: {
          title: 'public.users',
          badges: { pk: true, fk: false },
          columns: [
            { column_name: 'id', data_type: 'integer', is_pk: true, is_not_null: true },
            { column_name: 'name', data_type: 'varchar', is_pk: false, is_not_null: true },
          ],
        },
      },
    ];
    const result = exportDbml(nodes, []);
    expect(result).toContain('Table public.users {');
    expect(result).toContain('id integer [pk]');
    expect(result).toContain('name varchar [not null]');
  });

  it('should export relation', () => {
    const nodes: Node<TableNodeData>[] = [
      {
        id: '1',
        type: 'tableNode',
        position: { x: 0, y: 0 },
        data: {
          title: 'users',
          badges: { pk: true, fk: false },
          columns: [
            { column_name: 'id', data_type: 'int', is_pk: true, is_not_null: true },
          ],
        },
      },
      {
        id: '2',
        type: 'tableNode',
        position: { x: 0, y: 0 },
        data: {
          title: 'posts',
          badges: { pk: true, fk: true },
          columns: [
            { column_name: 'id', data_type: 'int', is_pk: true, is_not_null: true },
            { column_name: 'user_id', data_type: 'int', is_pk: false, is_not_null: true },
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
        label: 'rel',
      },
    ];

    const result = exportDbml(nodes, edges);
    expect(result).toContain('Ref: posts.user_id > users.id');
  });

  it('should export composite relation', () => {
    const nodes: Node<TableNodeData>[] = [
      {
        id: '1',
        type: 'tableNode',
        position: { x: 0, y: 0 },
        data: {
          title: 'users',
          badges: { pk: true, fk: false },
          columns: [
            { column_name: 'tenant_id', data_type: 'int', is_pk: true, is_not_null: true },
            { column_name: 'id', data_type: 'int', is_pk: true, is_not_null: true },
          ],
        },
      },
      {
        id: '2',
        type: 'tableNode',
        position: { x: 0, y: 0 },
        data: {
          title: 'posts',
          badges: { pk: true, fk: true },
          columns: [
            { column_name: 'id', data_type: 'int', is_pk: true, is_not_null: true },
            { column_name: 'tenant_id', data_type: 'int', is_pk: false, is_not_null: true },
            { column_name: 'user_id', data_type: 'int', is_pk: false, is_not_null: true },
          ],
        },
      },
    ];

    const edges: Edge[] = [
      {
        id: 'e1',
        source: '2',
        target: '1',
        label: 'rel',
        data: {
          sourceColumns: ['tenant_id', 'user_id'],
          targetColumns: ['tenant_id', 'id']
        }
      },
    ];

    const result = exportDbml(nodes, edges);
    expect(result).toContain('Ref: posts.(tenant_id, user_id) > users.(tenant_id, id)');
  });

  it('should escape special characters', () => {
    const nodes: Node<TableNodeData>[] = [
      {
        id: '1',
        type: 'tableNode',
        position: { x: 0, y: 0 },
        data: {
          title: 'public.my-table',
          comment: "test ' comment",
          badges: { pk: true, fk: false },
          columns: [
            { column_name: 'my-col', data_type: 'integer', is_pk: true, is_not_null: true, column_comment: "col ' comment" },
          ],
        },
      },
    ];
    const result = exportDbml(nodes, []);
    expect(result).toContain('Table public."my-table" {');
    expect(result).toContain('"my-col" integer [pk, note: \'col \'\' comment\']');
    expect(result).toContain('Note: \'test \'\' comment\'');
  });
});
