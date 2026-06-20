import type { Edge, Node } from '@xyflow/react'

import type { BusinessGroup } from './businessGroups'
import type { IndexRecommendation } from './cardinality'
import { sourceColumnHandleId, targetColumnHandleId } from './handleUtils'
import { GRID_COLUMNS, GRID_X_GAP, GRID_Y_GAP } from './layoutConstants'

type SnapshotJson = {
  relations: Array<{ relation_oid: number; relation_kind: string; schema_name: string; relation_name: string; relation_comment?: string | null }>
  columns: Array<{ relation_oid: number; column_name: string; data_type: string; is_not_null: boolean; column_comment?: string | null; example_value?: string | number | boolean | null }>
  constraints: Array<{
    constraint_oid: number
    constraint_name: string
    constraint_type: string
    schema_name: string
    relation_oid: number
    relation_name: string
    foreign_relation_oid?: number | null
    foreign_schema_name?: string | null
    foreign_relation_name?: string | null
    constrained_attnums?: number[] | null
    referenced_attnums?: number[] | null
    fk_on_update?: string | null
    fk_on_delete?: string | null
    fk_match_type?: string | null
    constraint_def?: string | null
    check_expr?: string | null
  }>
  pk_columns?: Array<{ relation_oid: number; column_name: string }>
  fk_edges?: Array<{
    fk_constraint_oid: number
    fk_constraint_name: string
    child_relation_oid: number
    parent_relation_oid: number
    child_column_name: string
    parent_column_name: string
    column_ordinal: number
  }>
}

export type TableNodeData = {
  title: string
  comment?: string | null
  columns: Array<{ column_name: string; data_type: string; is_not_null: boolean; is_pk: boolean; column_comment?: string | null; example_value?: string | number | boolean | null }>
  indexes?: IndexRecommendation[]
  businessGroup?: BusinessGroup | null
  badges: {
    pk: boolean
    fk: boolean
  }
}

export function snapshotToGraph(snapshot: SnapshotJson): { nodes: Array<Node<TableNodeData>>; edges: Edge[] } {
  const tableRels = snapshot.relations.filter((r) => r.relation_kind === 'r' || r.relation_kind === 'p')
  const pkColsByRel = new Map<number, Set<string>>()
  for (const p of snapshot.pk_columns || []) {
    const set = pkColsByRel.get(p.relation_oid) || new Set<string>()
    set.add(p.column_name)
    pkColsByRel.set(p.relation_oid, set)
  }

  const columnsByRel = new Map<number, TableNodeData['columns']>()
  for (const c of snapshot.columns) {
    const list = columnsByRel.get(c.relation_oid) || []
    const isPk = pkColsByRel.get(c.relation_oid)?.has(c.column_name) || false
    list.push({ column_name: c.column_name, data_type: c.data_type, is_not_null: c.is_not_null, is_pk: isPk, column_comment: c.column_comment, example_value: c.example_value })
    columnsByRel.set(c.relation_oid, list)
  }

  const hasPk = new Set<number>()
  for (const p of snapshot.pk_columns || []) {
    hasPk.add(p.relation_oid)
  }

  const hasFk = new Set<number>()
  const fkEdges: Array<{
    id: string
    source: string
    target: string
    sourceHandle?: string
    targetHandle?: string
    label: string
  }> = []

  const fkRows = snapshot.fk_edges || []
  if (fkRows.length > 0) {
    const grouped = new Map<number, typeof fkRows>()
    for (const r of fkRows) {
      // ponytail: previous array spreading copied each group on every row;
      // pushing keeps grouping O(n), with O(1) amortized append per row.
      const arr = grouped.get(r.fk_constraint_oid)
      if (arr) {
        arr.push(r)
      } else {
        grouped.set(r.fk_constraint_oid, [r])
      }
      hasFk.add(r.child_relation_oid)
    }
    for (const [oid, rows] of grouped.entries()) {
      const first = rows[0]
      const source = String(first.child_relation_oid)
      const target = String(first.parent_relation_oid)
      let sourceHandle: string | undefined = undefined
      let targetHandle: string | undefined = undefined
      let label = ''

      if (rows.length === 1) {
        label = `${first.fk_constraint_name}: ${first.child_column_name} → ${first.parent_column_name}`
        sourceHandle = sourceColumnHandleId(first.child_column_name)
        targetHandle = targetColumnHandleId(first.parent_column_name)
      } else {
        label = `${first.fk_constraint_name} (${rows.length} cols)`
      }

      fkEdges.push({ id: String(oid), source, target, sourceHandle, targetHandle, label })
    }
  } else {
    // Backward compat: infer FKs from constraints list only.
    for (const con of snapshot.constraints) {
      if (con.constraint_type === 'p') {
        if (typeof con.relation_oid === 'number') hasPk.add(con.relation_oid)
      }
      if (con.constraint_type === 'f') {
        const src = String(con.relation_oid)
        const dst = String(con.foreign_relation_oid)
        const id = String(con.constraint_oid)
        fkEdges.push({ id, source: src, target: dst, label: con.constraint_name })
        if (typeof con.relation_oid === 'number') hasFk.add(con.relation_oid)
      }
    }
  }

  const nodes: Array<Node<TableNodeData>> = tableRels.map((t, i) => {
    const cols = columnsByRel.get(t.relation_oid) || []
    return {
      id: String(t.relation_oid),
      type: 'tableNode',
      position: { x: (i % GRID_COLUMNS) * GRID_X_GAP, y: Math.floor(i / GRID_COLUMNS) * GRID_Y_GAP },
      data: {
        title: `${t.schema_name}.${t.relation_name}`,
        comment: t.relation_comment,
        columns: cols,
        badges: {
          pk: hasPk.has(t.relation_oid),
          fk: hasFk.has(t.relation_oid)
        }
      }
    }
  })

  const edges: Edge[] = fkEdges.map((e) => ({
    id: e.id,
    source: e.source,
    target: e.target,
    sourceHandle: e.sourceHandle,
    targetHandle: e.targetHandle,
    label: e.label,
    animated: false,
    type: 'smoothstep'
  }))

  return { nodes, edges }
}
