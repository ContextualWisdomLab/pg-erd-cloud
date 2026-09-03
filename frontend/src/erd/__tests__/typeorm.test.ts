import { describe, it, expect } from 'vitest';
import { exportTypeOrm } from '../typeorm';
import type { Node, Edge } from '@xyflow/react';
import type { TableNodeData } from '../convert';

describe('exportTypeOrm', () => {
  it('returns empty string when no tables', () => {
    const result = exportTypeOrm([], []);
    expect(result).toBe('// No tables to export\n');
  });

  it('exports a single table with primary key and columns', () => {
    const nodes: Node<TableNodeData>[] = [
      {
        id: '1',
        position: { x: 0, y: 0 },
        data: {
          title: 'users',
          columns: [
            { column_name: 'id', data_type: 'uuid', is_pk: true, is_not_null: true },
            { column_name: 'email', data_type: 'varchar', is_pk: false, is_not_null: true },
            { column_name: 'age', data_type: 'int', is_pk: false, is_not_null: false },
          ],
        },
      },
    ];

    const result = exportTypeOrm(nodes, []);
    expect(result).toContain("import { Entity, PrimaryColumn, PrimaryGeneratedColumn, Column, ManyToOne, OneToMany, JoinColumn } from 'typeorm';");
    expect(result).toContain("@Entity({ name: 'users' })");
    expect(result).toContain("export class Users {");
    expect(result).toContain("@PrimaryColumn()");
    expect(result).toContain("id!: string;");
    expect(result).toContain("@Column()");
    expect(result).toContain("email!: string;");
    expect(result).toContain("@Column({ nullable: true })");
    expect(result).toContain("age?: number | null;");
  });

  it('exports relations', () => {
    const nodes: Node<TableNodeData>[] = [
      {
        id: '1',
        position: { x: 0, y: 0 },
        data: {
          title: 'users',
          columns: [
            { column_name: 'id', data_type: 'uuid', is_pk: true, is_not_null: true },
          ],
        },
      },
      {
        id: '2',
        position: { x: 0, y: 0 },
        data: {
          title: 'posts',
          columns: [
            { column_name: 'id', data_type: 'uuid', is_pk: true, is_not_null: true },
            { column_name: 'user_id', data_type: 'uuid', is_pk: false, is_not_null: true },
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
      },
    ];

    const result = exportTypeOrm(nodes, edges);
    expect(result).toContain("@ManyToOne(() => Users)");
    expect(result).toContain("@JoinColumn({ name: 'user_id' })");
    expect(result).toContain("Users_user_id?: Users;");

    // Check one to many back relation
    expect(result).toContain("@OneToMany(() => Posts, (child) => child.Users_user_id)");
    expect(result).toContain("posts?: Posts[];");
  });
});
