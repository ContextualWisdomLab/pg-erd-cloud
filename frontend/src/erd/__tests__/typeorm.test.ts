import { describe, it, expect } from 'vitest';
import { exportTypeorm } from '../typeorm';
import type { Node, Edge } from '@xyflow/react';
import type { TableNodeData } from '../convert';
describe('exportTypeorm', () => {
  it('returns empty message when nodes are empty', () => {
    const result = exportTypeorm([], []);
    expect(result).toBe('// No tables to export\n');
  });
  it('exports a simple table with columns', () => {
    const nodes: Node<TableNodeData>[] = [{ id: '1', type: 'tableNode', position: { x: 0, y: 0 }, data: { title: 'users', badges: { pk: true, fk: false }, columns: [{ column_name: 'id', data_type: 'integer', is_pk: true, is_not_null: true }, { column_name: 'name', data_type: 'text', is_pk: false, is_not_null: false }] } }];
    const result = exportTypeorm(nodes, []);
    expect(result).toContain('export class Users');
    expect(result).toContain('@PrimaryColumn()');
    expect(result).toContain('id!: number;');
    expect(result).toContain('@Column({ nullable: true })');
    expect(result).toContain('name?: string | null;');
  });
  it('handles schemas correctly', () => {
    const nodes: Node<TableNodeData>[] = [{ id: '1', type: 'tableNode', position: { x: 0, y: 0 }, data: { title: 'auth.users', badges: { pk: true, fk: false }, columns: [{ column_name: 'id', data_type: 'integer', is_pk: true, is_not_null: true }] } }];
    const result = exportTypeorm(nodes, []);
    expect(result).toContain('@Entity({ name: "users", schema: "auth" })');
    expect(result).toContain('export class Users');
  });
  it('handles relations correctly', () => {
    const nodes: Node<TableNodeData>[] = [
      { id: '1', type: 'tableNode', position: { x: 0, y: 0 }, data: { title: 'users', badges: { pk: true, fk: false }, columns: [{ column_name: 'id', data_type: 'integer', is_pk: true, is_not_null: true }] } },
      { id: '2', type: 'tableNode', position: { x: 0, y: 0 }, data: { title: 'posts', badges: { pk: true, fk: true }, columns: [{ column_name: 'id', data_type: 'integer', is_pk: true, is_not_null: true }, { column_name: 'user_id', data_type: 'integer', is_pk: false, is_not_null: true }] } }
    ];
    const edges: Edge[] = [{ id: 'e1', source: '2', target: '1', sourceHandle: 'src-user_id', targetHandle: 'tgt-id' }];
    const result = exportTypeorm(nodes, edges);
    expect(result).toContain('@ManyToOne(() => Users)');
    expect(result).toContain('@JoinColumn({ name: "user_id" })');
    expect(result).toContain('user?: Users;');
    expect(result).toContain('@OneToMany(() => Posts, (child) => child)');
    expect(result).toContain('posts?: Posts[];');
  });
  it('handles invalid names safely', () => {
    const nodes: Node<TableNodeData>[] = [{ id: '1', type: 'tableNode', position: { x: 0, y: 0 }, data: { title: '123_table', badges: { pk: true, fk: false }, columns: [{ column_name: '123_col', data_type: 'integer', is_pk: true, is_not_null: true }] } }];
    const result = exportTypeorm(nodes, []);
    expect(result).toContain('export class Entity_123_table');
    expect(result).toContain('name: "123_col"');
    expect(result).toContain('field_123_col!: number;');
  });
  it('maps pg types to TypeORM types correctly', () => {
    const nodes: Node<TableNodeData>[] = [{
      id: '1', type: 'tableNode', position: { x: 0, y: 0 }, data: {
        title: 'types_table', badges: { pk: true, fk: false }, columns: [
          { column_name: 'c_int', data_type: 'integer', is_pk: true, is_not_null: true },
          { column_name: 'c_float', data_type: 'float', is_pk: false, is_not_null: true },
          { column_name: 'c_bool', data_type: 'boolean', is_pk: false, is_not_null: true },
          { column_name: 'c_date', data_type: 'timestamp', is_pk: false, is_not_null: true },
          { column_name: 'c_json', data_type: 'jsonb', is_pk: false, is_not_null: true },
          { column_name: 'c_bytea', data_type: 'bytea', is_pk: false, is_not_null: true },
          { column_name: 'c_text', data_type: 'text', is_pk: false, is_not_null: true },
          { column_name: 'c_uuid', data_type: 'uuid', is_pk: false, is_not_null: true },
        ]
      }
    }];
    const result = exportTypeorm(nodes, []);
    expect(result).toContain('c_int!: number;');
    expect(result).toContain('c_float!: number;');
    expect(result).toContain('c_bool!: boolean;');
    expect(result).toContain('c_date!: Date;');
    expect(result).toContain('c_json!: object;');
    expect(result).toContain('c_bytea!: Buffer;');
    expect(result).toContain('c_text!: string; // text');
    expect(result).toContain('c_uuid!: string;');
  });
});
