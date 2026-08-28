import { describe, it, expect } from 'vitest';
import { exportGraphql } from '../graphql';
import type { Node, Edge } from '@xyflow/react';
import type { TableNodeData } from '../convert';

describe('exportGraphql', () => {
  it('should return empty string for no nodes', () => {
    expect(exportGraphql([], [])).toBe('');
  });

  it('should generate basic types correctly', () => {
    const nodes: Node<TableNodeData>[] = [
      {
        id: '1',
        type: 'table',
        position: { x: 0, y: 0 },
        data: {
          title: 'public.users',
          badges: { pk: true, fk: false },
          columns: [
            { column_name: 'id', data_type: 'uuid', is_pk: true, is_not_null: true },
            { column_name: 'email', data_type: 'varchar', is_not_null: true, is_pk: false },
            { column_name: 'age', data_type: 'int', is_pk: false, is_not_null: false }
          ]
        }
      }
    ];

    const result = exportGraphql(nodes, []);
    expect(result).toContain('type Users {');
    expect(result).toContain('id: ID!');
    expect(result).toContain('email: String!');
    expect(result).toContain('age: Int');
  });

  it('should generate relations for edges', () => {
    const nodes: Node<TableNodeData>[] = [
      {
        id: '1',
        type: 'table',
        position: { x: 0, y: 0 },
        data: {
          title: 'users',
          badges: { pk: true, fk: false },
          columns: [
            { column_name: 'id', data_type: 'uuid', is_pk: true, is_not_null: true }
          ]
        }
      },
      {
        id: '2',
        type: 'table',
        position: { x: 0, y: 0 },
        data: {
          title: 'posts',
          badges: { pk: true, fk: false },
          columns: [
            { column_name: 'id', data_type: 'uuid', is_pk: true, is_not_null: true },
            { column_name: 'user_id', data_type: 'uuid', is_pk: false, is_not_null: false }
          ]
        }
      }
    ];

    const edges: Edge[] = [
      {
        id: 'e1',
        source: '2', // foreign key is on posts
        target: '1', // pointing to users
        sourceHandle: 'src-user_id',
        targetHandle: 'tgt-id'
      }
    ];

    const result = exportGraphql(nodes, edges);

    // Check Users type has posts
    expect(result).toMatch(/type Users \{[\s\S]*posts: \[Posts!\]![\s\S]*\}/);
    // Check Posts type has users relation (named users or user)
    expect(result).toMatch(/type Posts \{[\s\S]*users: Users[\s\S]*\}/);
  });

  it('should handle table comments', () => {
    const nodes: Node<TableNodeData>[] = [
      {
        id: '1',
        type: 'table',
        position: { x: 0, y: 0 },
        data: {
          title: 'public.users',
          comment: 'User accounts table',
          badges: { pk: true, fk: false },
          columns: []
        }
      }
    ];

    const result = exportGraphql(nodes, []);
    expect(result).toContain('"""\nUser accounts table\n"""');
  });
});
