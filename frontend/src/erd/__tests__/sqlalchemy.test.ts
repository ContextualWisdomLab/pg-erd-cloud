import { describe, it, expect } from 'vitest';
import { exportSqlAlchemy } from '../sqlalchemy';
import type { Node, Edge } from '@xyflow/react';
import type { TableNodeData } from '../convert';

describe('exportSqlAlchemy', () => {
  it('returns empty string when no tables', () => {
    const result = exportSqlAlchemy([], []);
    expect(result).toBe('# No tables to export\n');
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

    const result = exportSqlAlchemy(nodes, []);
    expect(result).toContain("class Users(Base):");
    expect(result).toContain("__tablename__ = 'users'");
    expect(result).toContain("id: Mapped[uuid.UUID] = mapped_column(primary_key=True)");
    expect(result).toContain("email: Mapped[str] = mapped_column()");
    expect(result).toContain("age: Mapped[int | None] = mapped_column()");
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

    const result = exportSqlAlchemy(nodes, edges);
    expect(result).toContain("user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id'))");
  });
});
