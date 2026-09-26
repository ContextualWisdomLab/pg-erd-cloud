import { describe, it, expect } from 'vitest';
import { exportSqlAlchemy } from '../sqlalchemy';
import type { Node } from '@xyflow/react';
import type { TableNodeData } from '../convert';

describe('exportSqlAlchemy', () => {
  it('returns empty comment if no nodes', () => {
    const result = exportSqlAlchemy([]);
    expect(result).toBe('# No tables to export\n');
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

    const result = exportSqlAlchemy(nodes);
    expect(result).toContain('class Users(Base):');
    expect(result).toContain('__tablename__ = \'users\'');
    expect(result).toContain('id = Column(Integer, primary_key=True)');
    expect(result).toContain('name = Column(String, nullable=True)');
  });
});
