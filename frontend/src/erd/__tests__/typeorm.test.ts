import { describe, it, expect } from 'vitest';
import { exportTypeORM } from '../typeorm';
import type { Node } from '@xyflow/react';
import type { TableNodeData } from '../convert';

describe('exportTypeORM', () => {
  it('returns empty comment if no nodes', () => {
    const result = exportTypeORM([]);
    expect(result).toBe('// No tables to export\n');
  });

  it('exports simple model correctly', () => {
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
            { column_name: 'name', data_type: 'varchar(255)', is_not_null: false, is_pk: false },
          ],
        },
      },
    ];

    const result = exportTypeORM(nodes);
    expect(result).toContain('@Entity("users")');
    expect(result).toContain('export class Users {');
    expect(result).toContain('@PrimaryColumn({ type: "int" })');
    expect(result).toContain('id!: number;');
    expect(result).toContain('@Column({ type: "varchar", nullable: true })');
    expect(result).toContain('name?: string;');
  });
});
