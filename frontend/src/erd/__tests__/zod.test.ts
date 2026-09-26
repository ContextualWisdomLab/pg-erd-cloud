import { describe, it, expect } from 'vitest';
import { exportZod } from '../zod';
import type { Node } from '@xyflow/react';
import type { TableNodeData } from '../convert';

describe('exportZod', () => {
  it('returns empty comment if no nodes', () => {
    const result = exportZod([]);
    expect(result).toBe('// No tables to export\n');
  });

  it('exports simple model correctly', () => {
    const nodes: Node<TableNodeData>[] = [
      {
        id: '1',
        type: 'tableNode',
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

    const result = exportZod(nodes);
    expect(result).toContain('export const UsersSchema = z.object({');
    expect(result).toContain('id: z.number(),');
    expect(result).toContain('name: z.string().nullable(),');
    expect(result).toContain('export type Users = z.infer<typeof UsersSchema>;');
  });
});
