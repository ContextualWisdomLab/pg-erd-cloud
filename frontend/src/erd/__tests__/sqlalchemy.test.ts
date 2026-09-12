import { describe, it, expect } from 'vitest';
import { exportSqlalchemy } from '../sqlalchemy';
import type { Node, Edge } from '@xyflow/react';
import type { TableNodeData } from '../convert';

describe('exportSqlalchemy', () => {
  it('exports empty state correctly', () => {
    const result = exportSqlalchemy([], []);
    expect(result).toBe('# No tables to export\n');
  });

  it('exports simple model correctly', () => {
    const nodes: Node<TableNodeData>[] = [
      {
        id: '1',
        position: { x: 0, y: 0 },
        data: {
          title: 'users',
          columns: [
            { column_name: 'id', data_type: 'uuid', is_pk: true, is_not_null: true },
            { column_name: 'email', data_type: 'varchar', is_pk: false, is_not_null: true },
            { column_name: 'created_at', data_type: 'timestamp', is_pk: false, is_not_null: false },
          ],
          badges: { pk: true, fk: false },
        },
      },
    ];

    const result = exportSqlalchemy(nodes, []);

    expect(result).toContain('class User(Base):');
    expect(result).toContain("__tablename__ = 'users'");
    expect(result).toContain('id = Column(Uuid, primary_key=True)');
    expect(result).toContain('email = Column(String, unique=True, nullable=False)');
    expect(result).toContain('created_at = Column(DateTime)');
  });

  it('exports models with foreign keys and relationships correctly', () => {
    const nodes: Node<TableNodeData>[] = [
      {
        id: '1',
        position: { x: 0, y: 0 },
        data: {
          title: 'users',
          columns: [
            { column_name: 'id', data_type: 'int', is_pk: true, is_not_null: true },
          ],
          badges: { pk: true, fk: false },
        },
      },
      {
        id: '2',
        position: { x: 0, y: 0 },
        data: {
          title: 'posts',
          columns: [
            { column_name: 'id', data_type: 'int', is_pk: true, is_not_null: true },
            { column_name: 'user_id', data_type: 'int', is_pk: false, is_not_null: true },
          ],
          badges: { pk: true, fk: true },
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

    const result = exportSqlalchemy(nodes, edges);

    expect(result).toContain('class User(Base):');
    expect(result).toContain("postss = relationship('Post', foreign_keys='[Post.user_id]')");

    expect(result).toContain('class Post(Base):');
    expect(result).toContain("user_id = Column(Integer, nullable=False, ForeignKey('users.id'))");
    expect(result).toContain("users = relationship('User', foreign_keys=[user_id])");
  });

  it('exports models with schemas correctly', () => {
    const nodes: Node<TableNodeData>[] = [
      {
        id: '1',
        position: { x: 0, y: 0 },
        data: {
          title: 'public.users',
          columns: [
            { column_name: 'id', data_type: 'int', is_pk: true, is_not_null: true },
          ],
          badges: { pk: true, fk: false },
        },
      },
    ];

    const result = exportSqlalchemy(nodes, []);

    expect(result).toContain('class PublicUser(Base):');
    expect(result).toContain("__tablename__ = 'users'");
    expect(result).toContain("__table_args__ = {'schema': 'public'}");
  });

  it('handles reserved python keywords as field names', () => {
    const nodes: Node<TableNodeData>[] = [
      {
        id: '1',
        position: { x: 0, y: 0 },
        data: {
          title: 'python_table',
          columns: [
            { column_name: 'class', data_type: 'varchar', is_pk: false, is_not_null: false },
            { column_name: 'def', data_type: 'varchar', is_pk: false, is_not_null: false },
          ],
          badges: { pk: false, fk: false },
        },
      },
    ];

    const result = exportSqlalchemy(nodes, []);
    expect(result).toContain('class_ = Column(String)');
    expect(result).toContain('def_ = Column(String)');
  });

  it('handles edges with missing handles gracefully', () => {
    const nodes: Node<TableNodeData>[] = [
      {
        id: '1',
        position: { x: 0, y: 0 },
        data: {
          title: 'users',
          columns: [
            { column_name: 'id', data_type: 'int', is_pk: true, is_not_null: true },
          ],
          badges: { pk: true, fk: false },
        },
      },
      {
        id: '2',
        position: { x: 0, y: 0 },
        data: {
          title: 'posts',
          columns: [
            { column_name: 'id', data_type: 'int', is_pk: true, is_not_null: true },
          ],
          badges: { pk: true, fk: true },
        },
      },
    ];

    const edges: Edge[] = [
      {
        id: 'e1',
        source: '2',
        target: '1',
      },
    ];

    const result = exportSqlalchemy(nodes, edges);
    // Should not crash, should generate base tables without relationships
    expect(result).toContain('class User(Base):');
    expect(result).toContain('class Post(Base):');
  });

  it('handles various data types properly', () => {
    const nodes: Node<TableNodeData>[] = [
      {
        id: '1',
        position: { x: 0, y: 0 },
        data: {
          title: 'types',
          columns: [
            { column_name: 'col1', data_type: 'serial', is_pk: true, is_not_null: true },
            { column_name: 'col2', data_type: 'bigint', is_pk: false, is_not_null: false },
            { column_name: 'col3', data_type: 'smallint', is_pk: false, is_not_null: false },
            { column_name: 'col4', data_type: 'float8', is_pk: false, is_not_null: false },
            { column_name: 'col5', data_type: 'numeric', is_pk: false, is_not_null: false },
            { column_name: 'col6', data_type: 'json', is_pk: false, is_not_null: false },
            { column_name: 'col7', data_type: 'bytea', is_pk: false, is_not_null: false },
            { column_name: 'col8', data_type: 'time', is_pk: false, is_not_null: false },
            { column_name: 'col9', data_type: 'date', is_pk: false, is_not_null: false },
            { column_name: 'col10', data_type: 'bool', is_pk: false, is_not_null: false },
            { column_name: 'col11', data_type: 'unknown', is_pk: false, is_not_null: false },
          ],
          badges: { pk: true, fk: false },
        },
      },
    ];

    const result = exportSqlalchemy(nodes, []);
    expect(result).toContain('col1 = Column(Integer, primary_key=True)');
    expect(result).toContain('col2 = Column(BigInteger)');
    expect(result).toContain('col3 = Column(SmallInteger)');
    expect(result).toContain('col4 = Column(Float)');
    expect(result).toContain('col5 = Column(Numeric)');
    expect(result).toContain('col6 = Column(JSON)');
    expect(result).toContain('col7 = Column(LargeBinary)');
    expect(result).toContain('col8 = Column(Time)');
    expect(result).toContain('col9 = Column(Date)');
    expect(result).toContain('col10 = Column(Boolean)');
    expect(result).toContain('col11 = Column(String)');
  });

  it('disambiguates relationships with same name', () => {
      const nodes: Node<TableNodeData>[] = [
        {
          id: '1',
          position: { x: 0, y: 0 },
          data: {
            title: 'users',
            columns: [
              { column_name: 'id', data_type: 'int', is_pk: true, is_not_null: true },
            ],
            badges: { pk: true, fk: false },
          },
        },
        {
          id: '2',
          position: { x: 0, y: 0 },
          data: {
            title: 'posts',
            columns: [
              { column_name: 'id', data_type: 'int', is_pk: true, is_not_null: true },
              { column_name: 'author_id', data_type: 'int', is_pk: false, is_not_null: true },
              { column_name: 'editor_id', data_type: 'int', is_pk: false, is_not_null: true },
            ],
            badges: { pk: true, fk: true },
          },
        },
      ];

      const edges: Edge[] = [
        {
          id: 'e1',
          source: '2',
          target: '1',
          sourceHandle: 'src-author_id',
          targetHandle: 'tgt-id',
        },
        {
          id: 'e2',
          source: '2',
          target: '1',
          sourceHandle: 'src-editor_id',
          targetHandle: 'tgt-id',
        },
      ];

      const result = exportSqlalchemy(nodes, edges);

      expect(result).toContain("users = relationship('User', foreign_keys=[author_id])");
      expect(result).toContain("users_editor_id = relationship('User', foreign_keys=[editor_id])");

      expect(result).toContain("postss = relationship('Post', foreign_keys='[Post.author_id]')");
      expect(result).toContain("postss_editor_id = relationship('Post', foreign_keys='[Post.editor_id]')");
    });
});
