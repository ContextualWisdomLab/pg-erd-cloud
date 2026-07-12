import { describe, it, expect } from 'vitest';
import { exportDbml } from '../dbml';
import type { Node, Edge } from '@xyflow/react';
import type { TableNodeData } from '../convert';

describe('exportDbml', () => {
  it('returns empty string when nodes are empty', () => {
    const nodes: Node<TableNodeData>[] = [];
    const edges: Edge[] = [];
    const result = exportDbml(nodes, edges);
    expect(result).toBe('');
  });

  it('exports tables and columns and escapes quotes and backslashes', () => {
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
            { column_name: 'username', data_type: 'varchar', is_not_null: false, is_pk: false, column_comment: 'login\'s name \\ char' }
          ],
          comment: 'user\'s table \\ test'
        }
      }
    ];
    const result = exportDbml(nodes, []);
    expect(result).toContain('Table "public.users" {');
    expect(result).toContain('  "id" "integer" [pk, not null]');
    expect(result).toContain('  "username" "varchar" [note: \'login\\\'s name \\\\ char\']');
    expect(result).toContain('  Note: \'user\\\'s table \\\\ test\'');
  });

  it('exports relations correctly', () => {
    const nodes: Node<TableNodeData>[] = [
      {
        id: '1',
        type: 'tableNode',
        position: { x: 0, y: 0 },
        data: { title: 't1', badges: { pk: true, fk: false }, columns: [] }
      },
      {
        id: '2',
        type: 'tableNode',
        position: { x: 0, y: 0 },
        data: { title: 't2', badges: { pk: false, fk: true }, columns: [] }
      }
    ];
    const edges: Edge[] = [
      {
        id: 'e1',
        source: '2',
        target: '1',
        type: 'smoothstep',
        data: {
          sourceColumns: ['t2_fk'],
          targetColumns: ['t1_pk']
        }
      }
    ];
    const result = exportDbml(nodes, edges);
    expect(result).toContain('Ref: "t2"."t2_fk" > "t1"."t1_pk"');
  });
});
