import { describe, it, expect } from 'vitest'
import { snapshotToGraph } from './convert'

type SnapshotInput = Parameters<typeof snapshotToGraph>[0]

describe('snapshotToGraph', () => {
  it('converts relations to nodes and columns', () => {
    const snapshot: SnapshotInput = {
      relations: [
        { relation_oid: 1, relation_kind: 'r', schema_name: 'public', relation_name: 'users', relation_comment: 'User accounts' }
      ],
      columns: [
        { relation_oid: 1, column_name: 'id', data_type: 'integer', is_not_null: true },
        { relation_oid: 1, column_name: 'name', data_type: 'text', is_not_null: false }
      ],
      constraints: []
    }

    const graph = snapshotToGraph(snapshot)

    expect(graph.nodes).toHaveLength(1)
    expect(graph.nodes[0].id).toBe('1')
    expect(graph.nodes[0].data.title).toBe('public.users')
    expect(graph.nodes[0].data.comment).toBe('User accounts')
    expect(graph.nodes[0].data.columns).toHaveLength(2)
    expect(graph.nodes[0].data.columns[0]).toMatchObject({
      column_name: 'id',
      data_type: 'integer',
      is_not_null: true,
      is_pk: false
    })

    expect(graph.edges).toHaveLength(0)
  })

  it('identifies primary keys correctly', () => {
    const snapshot: SnapshotInput = {
      relations: [
        { relation_oid: 1, relation_kind: 'r', schema_name: 'public', relation_name: 'users' }
      ],
      columns: [
        { relation_oid: 1, column_name: 'id', data_type: 'integer', is_not_null: true },
        { relation_oid: 1, column_name: 'name', data_type: 'text', is_not_null: false }
      ],
      constraints: [],
      pk_columns: [
        { relation_oid: 1, column_name: 'id' }
      ]
    }

    const graph = snapshotToGraph(snapshot)

    expect(graph.nodes[0].data.badges.pk).toBe(true)
    expect(graph.nodes[0].data.columns[0].is_pk).toBe(true)
    expect(graph.nodes[0].data.columns[1].is_pk).toBe(false)
  })

  it('identifies foreign keys correctly via fk_edges', () => {
    const snapshot: SnapshotInput = {
      relations: [
        { relation_oid: 1, relation_kind: 'r', schema_name: 'public', relation_name: 'users' },
        { relation_oid: 2, relation_kind: 'r', schema_name: 'public', relation_name: 'posts' }
      ],
      columns: [
        { relation_oid: 1, column_name: 'id', data_type: 'integer', is_not_null: true },
        { relation_oid: 2, column_name: 'id', data_type: 'integer', is_not_null: true },
        { relation_oid: 2, column_name: 'user_id', data_type: 'integer', is_not_null: true }
      ],
      constraints: [],
      fk_edges: [
        {
          fk_constraint_oid: 100,
          fk_constraint_name: 'fk_user',
          child_relation_oid: 2,
          parent_relation_oid: 1,
          child_column_name: 'user_id',
          parent_column_name: 'id',
          column_ordinal: 1
        }
      ]
    }

    const graph = snapshotToGraph(snapshot)

    expect(graph.edges).toHaveLength(1)
    expect(graph.edges[0]).toMatchObject({
      id: '100',
      source: '2',
      target: '1',
      label: 'fk_user: user_id → id'
    })

    expect(graph.nodes.find((n) => n.id === '2')?.data.badges.fk).toBe(true)
    expect(graph.nodes.find((n) => n.id === '1')?.data.badges.fk).toBe(false)
  })

  it('identifies composite foreign keys correctly via fk_edges', () => {
    const snapshot: SnapshotInput = {
      relations: [
        { relation_oid: 1, relation_kind: 'r', schema_name: 'public', relation_name: 'orgs' },
        { relation_oid: 2, relation_kind: 'r', schema_name: 'public', relation_name: 'users' }
      ],
      columns: [],
      constraints: [],
      fk_edges: [
        { fk_constraint_oid: 100, fk_constraint_name: 'fk_org_dept', child_relation_oid: 2, parent_relation_oid: 1, child_column_name: 'dept_id', parent_column_name: 'dept_id', column_ordinal: 2 },
        { fk_constraint_oid: 100, fk_constraint_name: 'fk_org_dept', child_relation_oid: 2, parent_relation_oid: 1, child_column_name: 'org_id', parent_column_name: 'id', column_ordinal: 1 }
      ]
    }

    const graph = snapshotToGraph(snapshot)

    expect(graph.edges).toHaveLength(1)
    expect(graph.edges[0].label).toBe('fk_org_dept (2 cols)')
    expect(graph.edges[0].data).toEqual({
      sourceColumns: ['org_id', 'dept_id'],
      targetColumns: ['id', 'dept_id'],
    })
  })

  it('falls back to constraints if fk_edges is empty or not provided', () => {
    const snapshot: SnapshotInput = {
      relations: [
        { relation_oid: 1, relation_kind: 'r', schema_name: 'public', relation_name: 'users' },
        { relation_oid: 2, relation_kind: 'r', schema_name: 'public', relation_name: 'posts' }
      ],
      columns: [],
      constraints: [
        {
          constraint_oid: 99,
          constraint_name: 'users_pkey',
          constraint_type: 'p',
          schema_name: 'public',
          relation_oid: 1,
          relation_name: 'users'
        },
        {
          constraint_oid: 100,
          constraint_name: 'fk_user_old',
          constraint_type: 'f',
          schema_name: 'public',
          relation_oid: 2,
          relation_name: 'posts',
          foreign_relation_oid: 1
        }
      ]
    }

    const graph = snapshotToGraph(snapshot)

    // node 1 is PK
    expect(graph.nodes.find((n) => n.id === '1')?.data.badges.pk).toBe(true)
    // node 2 is FK
    expect(graph.nodes.find((n) => n.id === '2')?.data.badges.fk).toBe(true)

    expect(graph.edges).toHaveLength(1)
    expect(graph.edges[0]).toMatchObject({
      id: '100',
      source: '2',
      target: '1',
      label: 'fk_user_old'
    })
  })

  it('handles empty snapshot gracefully', () => {
    const snapshot: SnapshotInput = {}
    const graph = snapshotToGraph(snapshot)
    expect(graph.nodes).toHaveLength(0)
    expect(graph.edges).toHaveLength(0)
  })

  it('includes partitioned tables and ignores other kinds like views', () => {
    const snapshot: SnapshotInput = {
      relations: [
        { relation_oid: 1, relation_kind: 'p', schema_name: 'public', relation_name: 'part_table' },
        { relation_oid: 2, relation_kind: 'v', schema_name: 'public', relation_name: 'view_table' }
      ]
    }
    const graph = snapshotToGraph(snapshot)
    expect(graph.nodes).toHaveLength(1)
    expect(graph.nodes[0].data.title).toBe('public.part_table')
  })

  it('handles constraints with invalid relation_oid types gracefully', () => {
    const snapshot: SnapshotInput = {
      relations: [
        { relation_oid: 1, relation_kind: 'r', schema_name: 'public', relation_name: 'users' },
        { relation_oid: 2, relation_kind: 'r', schema_name: 'public', relation_name: 'posts' }
      ],
      constraints: [
        {
          constraint_oid: 99,
          constraint_name: 'users_pkey',
          constraint_type: 'p',
          schema_name: 'public',
          relation_oid: undefined as any, // Not a number
          relation_name: 'users'
        },
        {
          constraint_oid: 100,
          constraint_name: 'fk_user_old',
          constraint_type: 'f',
          schema_name: 'public',
          relation_oid: 'string_id' as any, // Not a number
          relation_name: 'posts',
          foreign_relation_oid: 1
        }
      ]
    }

    const graph = snapshotToGraph(snapshot)
    expect(graph.nodes.find((n) => n.id === '1')?.data.badges.pk).toBe(false)
    expect(graph.nodes.find((n) => n.id === '2')?.data.badges.fk).toBe(false)

    // Edges are still created based on the constraint even if badges aren't updated
    expect(graph.edges).toHaveLength(1)
  })
})
