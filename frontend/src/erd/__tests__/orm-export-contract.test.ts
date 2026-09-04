import { describe, expect, it } from 'vitest';

import { snapshotToGraph } from '../convert';
import { exportSqlAlchemy } from '../sqlalchemy';
import { exportTypeOrm } from '../typeorm';

type SnapshotInput = Parameters<typeof snapshotToGraph>[0];

function relationshipSnapshot(): SnapshotInput {
  return {
    relations: [
      {
        relation_oid: 1,
        relation_kind: 'r',
        schema_name: 'public',
        relation_name: 'users',
      },
      {
        relation_oid: 2,
        relation_kind: 'r',
        schema_name: 'public',
        relation_name: 'posts',
      },
    ],
    columns: [
      {
        relation_oid: 1,
        column_name: 'tenant_id',
        data_type: 'uuid',
        is_not_null: true,
      },
      {
        relation_oid: 1,
        column_name: 'id',
        data_type: 'uuid',
        is_not_null: true,
      },
      {
        relation_oid: 2,
        column_name: 'tenant_id',
        data_type: 'uuid',
        is_not_null: true,
      },
      {
        relation_oid: 2,
        column_name: 'user_id',
        data_type: 'uuid',
        is_not_null: true,
      },
    ],
    constraints: [],
    pk_columns: [
      { relation_oid: 1, column_name: 'tenant_id' },
      { relation_oid: 1, column_name: 'id' },
    ],
    fk_edges: [
      {
        fk_constraint_oid: 100,
        fk_constraint_name: 'posts_user_fk',
        child_relation_oid: 2,
        parent_relation_oid: 1,
        child_column_name: 'tenant_id',
        parent_column_name: 'tenant_id',
        column_ordinal: 1,
      },
      {
        fk_constraint_oid: 100,
        fk_constraint_name: 'posts_user_fk',
        child_relation_oid: 2,
        parent_relation_oid: 1,
        child_column_name: 'user_id',
        parent_column_name: 'id',
        column_ordinal: 2,
      },
    ],
  };
}

describe('ORM export production graph contract', () => {
  it('preserves schema separately from the relation name', () => {
    const graph = snapshotToGraph(relationshipSnapshot());

    const sqlalchemy = exportSqlAlchemy(graph.nodes, graph.edges);
    const typeorm = exportTypeOrm(graph.nodes, graph.edges);

    expect(sqlalchemy).toContain("__tablename__ = 'users'");
    expect(sqlalchemy).toContain("__table_args__ = {'schema': 'public'}");
    expect(sqlalchemy).not.toContain("__tablename__ = 'public.users'");

    expect(typeorm).toContain("@Entity({ name: 'users', schema: 'public' })");
    expect(typeorm).not.toContain("@Entity({ name: 'public.users' })");
  });

  it('exports every column pair of a composite FK produced by snapshotToGraph', () => {
    const graph = snapshotToGraph(relationshipSnapshot());

    const sqlalchemy = exportSqlAlchemy(graph.nodes, graph.edges);
    const typeorm = exportTypeOrm(graph.nodes, graph.edges);

    expect(sqlalchemy).toContain("ForeignKey('public.users.tenant_id')");
    expect(sqlalchemy).toContain("ForeignKey('public.users.id')");
    expect(typeorm).toContain("name: 'tenant_id'");
    expect(typeorm).toContain("referencedColumnName: 'tenant_id'");
    expect(typeorm).toContain("name: 'user_id'");
    expect(typeorm).toContain("referencedColumnName: 'id'");
  });

  it('encodes database identifiers before placing them in generated code literals', () => {
    const snapshot: SnapshotInput = {
      relations: [
        {
          relation_oid: 1,
          relation_kind: 'r',
          schema_name: 'public',
          relation_name: "orders'\n__import__('os').system('pwn')",
        },
      ],
      columns: [
        {
          relation_oid: 1,
          column_name: "owner'\nconsole.log('pwn')",
          data_type: 'text',
          is_not_null: true,
        },
      ],
      constraints: [],
    };
    const graph = snapshotToGraph(snapshot);

    const sqlalchemy = exportSqlAlchemy(graph.nodes, graph.edges);
    const typeorm = exportTypeOrm(graph.nodes, graph.edges);

    expect(sqlalchemy).not.toContain("\n__import__('os').system('pwn')");
    expect(sqlalchemy).not.toContain("\nconsole.log('pwn')");
    expect(typeorm).not.toContain("\n__import__('os').system('pwn')");
    expect(typeorm).not.toContain("\nconsole.log('pwn')");
  });

  it('does not emit a Python keyword as a mapped attribute name', () => {
    const snapshot: SnapshotInput = {
      relations: [
        {
          relation_oid: 1,
          relation_kind: 'r',
          schema_name: 'public',
          relation_name: 'keywords',
        },
      ],
      columns: [
        {
          relation_oid: 1,
          column_name: 'class',
          data_type: 'text',
          is_not_null: true,
        },
      ],
      constraints: [],
    };
    const graph = snapshotToGraph(snapshot);
    const sqlalchemy = exportSqlAlchemy(graph.nodes, graph.edges);

    expect(sqlalchemy).not.toContain('    class: Mapped[');
    expect(sqlalchemy).toContain("mapped_column('class'");
  });
});
