import { describe, it, expect } from 'vitest';
import { exportMermaid } from '../mermaid';
import type { Node, Edge } from '@xyflow/react';
import type { TableNodeData } from '../convert';

describe('exportMermaid', () => {
  it('returns empty diagram when nodes are empty', () => {
    const nodes: Node<TableNodeData>[] = [];
    const edges: Edge[] = [];
    const result = exportMermaid(nodes, edges);
    expect(result).toBe('erDiagram\n');
  });

  it('exports nodes with columns and types', () => {
    const nodes: Node<TableNodeData>[] = [
      {
        id: '1',
        type: 'tableNode',
        position: { x: 0, y: 0 },
        data: {
          title: 'public.users',
          badges: { pk: true, fk: false },
          columns: [
            { column_name: 'id', data_type: 'integer', is_not_null: true, is_pk: true },
            { column_name: 'username', data_type: 'character varying(255)', is_not_null: true, is_pk: false }
          ]
        }
      }
    ];
    const edges: Edge[] = [];
    const result = exportMermaid(nodes, edges);
    expect(result).toContain('erDiagram\n');
    expect(result).toContain('  "public.users" {\n');
    expect(result).toContain('    integer id PK\n');
    expect(result).toContain('    character_varying_255_ username\n');
    expect(result).toContain('  }\n');
  });

  it('exports edges representing relations', () => {
    const nodes: Node<TableNodeData>[] = [
      {
        id: '1',
        type: 'tableNode',
        position: { x: 0, y: 0 },
        data: {
          title: 'public.users',
          badges: { pk: true, fk: false },
          columns: [
            { column_name: 'id', data_type: 'integer', is_not_null: true, is_pk: true }
          ]
        }
      },
      {
        id: '2',
        type: 'tableNode',
        position: { x: 0, y: 0 },
        data: {
          title: 'public.posts',
          badges: { pk: true, fk: true },
          columns: [
            { column_name: 'id', data_type: 'integer', is_not_null: true, is_pk: true },
            { column_name: 'user_id', data_type: 'integer', is_not_null: true, is_pk: false }
          ]
        }
      }
    ];
    const edges: Edge[] = [
      {
        id: 'e1',
        source: '2', // child has FK
        target: '1', // parent has PK
        sourceHandle: 'src-c-0075-0073-0065-0072-005f-0069-0064', // user_id
        targetHandle: 'tgt-c-0069-0064', // id
        label: 'fk_user_id',
        type: 'smoothstep'
      }
    ];
    const result = exportMermaid(nodes, edges);

    expect(result).toContain('    integer user_id FK\n');
    expect(result).toContain('  "public.users" ||--o{ "public.posts" : "fk_user_id"\n');
  });

  it('handles edges with missing nodes', () => {
    const nodes: Node<TableNodeData>[] = [
      {
        id: '1',
        type: 'tableNode',
        position: { x: 0, y: 0 },
        data: {
          title: 'public.users',
          badges: { pk: true, fk: false },
          columns: [
            { column_name: 'id', data_type: 'integer', is_not_null: true, is_pk: true }
          ]
        }
      }
    ];
    const edges: Edge[] = [
      {
        id: 'e1',
        source: '2', // Missing source
        target: '1',
        label: 'fk_missing',
        type: 'smoothstep'
      }
    ];
    const result = exportMermaid(nodes, edges);
    expect(result).not.toContain('||--o{');
  });

  it('handles edges without labels', () => {
    const nodes: Node<TableNodeData>[] = [
      {
        id: '1',
        type: 'tableNode',
        position: { x: 0, y: 0 },
        data: {
          title: 't1',
          badges: { pk: true, fk: false },
          columns: []
        }
      },
      {
        id: '2',
        type: 'tableNode',
        position: { x: 0, y: 0 },
        data: {
          title: 't2',
          badges: { pk: false, fk: true },
          columns: []
        }
      }
    ];
    const edges: Edge[] = [
      {
        id: 'e1',
        source: '2',
        target: '1',
        type: 'smoothstep'
      }
    ];
    const result = exportMermaid(nodes, edges);
    expect(result).toContain('  "t1" ||--o{ "t2" : "rel"\n');
  });

  it('handles fallback FK detection using node badges if handle is missing', () => {
    const nodes: Node<TableNodeData>[] = [
      {
        id: '1',
        type: 'tableNode',
        position: { x: 0, y: 0 },
        data: {
          title: 'public.posts',
          badges: { pk: true, fk: true }, // fk is true
          columns: [
            { column_name: 'user_id', data_type: 'integer', is_not_null: true, is_pk: false }
          ]
        }
      }
    ];
    const edges: Edge[] = [
      {
        id: 'e1',
        source: '1',
        target: '2',
        // missing sourceHandle
        type: 'smoothstep'
      }
    ];
    const result = exportMermaid(nodes, edges);
    expect(result).toContain('    integer user_id FK\n');
  });
  it('sanitizes titles, labels, and column names to prevent XSS', () => {
    const nodes: Node<TableNodeData>[] = [
      {
        id: '1',
        type: 'tableNode',
        position: { x: 0, y: 0 },
        data: {
          title: 'public."users"<script>alert(1)</script>',
          badges: { pk: true, fk: false },
          columns: [
            { column_name: 'i\'d', data_type: 'integer', is_not_null: true, is_pk: true }
          ]
        }
      },
      {
        id: '2',
        type: 'tableNode',
        position: { x: 0, y: 0 },
        data: {
          title: 'public.\'posts\'\n',
          badges: { pk: true, fk: true },
          columns: [
            { column_name: 'user\r_id', data_type: 'integer', is_not_null: true, is_pk: false }
          ]
        }
      }
    ];
    const edges: Edge[] = [
      {
        id: 'e1',
        source: '2',
        target: '1',
        label: 'fk_user_"id"<>',
        type: 'smoothstep'
      }
    ];
    const result = exportMermaid(nodes, edges);

    // Check that quotes and newlines were removed
    expect(result).not.toContain('<script>');
    expect(result).toContain('  "public.usersscriptalert(1)/script" {\n');
    expect(result).toContain('    integer id PK\n');
    expect(result).toContain('  "public.posts" {\n');
    expect(result).toContain('    integer user_id FK\n');
    expect(result).toContain('  "public.usersscriptalert(1)/script" ||--o{ "public.posts" : "fk_user_id"\n');
  });

  it('handles empty titles or missing labels safely', () => {
    const nodes: Node<TableNodeData>[] = [
      {
        id: '1',
        type: 'tableNode',
        position: { x: 0, y: 0 },
        data: {
          title: '', // empty title
          badges: { pk: true, fk: false },
          columns: [
            { column_name: '', data_type: 'integer', is_not_null: true, is_pk: true }
          ]
        }
      }
    ];
    const result = exportMermaid(nodes, []);
    expect(result).toContain('  "" {\n');
    expect(result).toContain('    integer  PK\n');
  });
});
