import type { Edge, Node } from '@xyflow/react'

type SnapshotJson = {
  relations: Array<{ relation_oid: number; relation_kind: string; schema_name: string; relation_name: string }>
  columns: Array<{ relation_oid: number; column_name: string; data_type: string; is_not_null: boolean }>
  constraints: Array<any>
}

export function snapshotToGraph(snapshot: SnapshotJson): { nodes: Node[]; edges: Edge[] } {
  const tableRels = snapshot.relations.filter((r) => r.relation_kind === 'r' || r.relation_kind === 'p')
  const columnsByRel = new Map<number, Array<{ column_name: string; data_type: string; is_not_null: boolean }>>()
  for (const c of snapshot.columns) {
    const list = columnsByRel.get(c.relation_oid) || []
    list.push({ column_name: c.column_name, data_type: c.data_type, is_not_null: c.is_not_null })
    columnsByRel.set(c.relation_oid, list)
  }

  const hasPk = new Set<number>()
  const hasFk = new Set<number>()
  const fkEdges: Array<{ id: string; source: string; target: string; label: string }> = []

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

  const nodes: Node[] = tableRels.map((t, i) => {
    const cols = columnsByRel.get(t.relation_oid) || []
    return {
      id: String(t.relation_oid),
      type: 'tableNode',
      position: { x: (i % 4) * 320, y: Math.floor(i / 4) * 220 },
      data: {
        title: `${t.schema_name}.${t.relation_name}`,
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
    label: e.label,
    animated: false
  }))

  return { nodes, edges }
}
