import type { Edge, Node } from '@xyflow/react'
import { describe, expect, it } from 'vitest'

import type { TableNodeData } from '../convert'
import { exportPrisma } from '../prisma'

function tableNode(
  nodeId: string,
  tableTitle: string,
  columns: TableNodeData['columns'],
): Node<TableNodeData> {
  return {
    id: nodeId,
    position: { x: 0, y: 0 },
    data: {
      title: tableTitle,
      badges: { pk: true, fk: false },
      columns,
    },
  }
}

describe('Prisma relation index', () => {
  it('preserves every large-diagram relation after one edge-indexing pass', () => {
    const relationshipCount = 96
    const sourceColumns: TableNodeData['columns'] = [
      {
        column_name: 'id',
        data_type: 'serial',
        is_pk: true,
        is_not_null: true,
      },
    ]
    const nodes: Node<TableNodeData>[] = []
    const edges: Edge[] = []

    for (let index = 0; index < relationshipCount; index += 1) {
      const sourceField = `target_${index}_id`
      sourceColumns.push({
        column_name: sourceField,
        data_type: 'integer',
        is_pk: false,
        is_not_null: true,
      })
      nodes.push(
        tableNode(`target-${index}`, `target_${index}`, [
          {
            column_name: 'id',
            data_type: 'serial',
            is_pk: true,
            is_not_null: true,
          },
        ]),
      )
      edges.push({
        id: `relation-${index}`,
        source: 'source-node',
        target: `target-${index}`,
        sourceHandle: `src-${sourceField}`,
        targetHandle: 'tgt-id',
        label: `relation_${index}`,
      })
    }

    nodes.unshift(tableNode('source-node', 'source_table', sourceColumns))

    for (let index = 0; index < relationshipCount * 4; index += 1) {
      edges.push({
        id: `unrelated-${index}`,
        source: `missing-source-${index}`,
        target: `target-${index % relationshipCount}`,
        sourceHandle: `src-noise_${index}`,
        targetHandle: 'tgt-id',
        label: `noise_${index}`,
      })
    }

    const schema = exportPrisma(nodes, edges)

    for (let index = 0; index < relationshipCount; index += 1) {
      expect(schema).toContain(
        `target_${index}_target_${index}_id target_${index} @relation("relation_${index}", fields: [target_${index}_id], references: [id])`,
      )
      expect(schema).toContain(
        `source_table_target_${index}_id source_table[] @relation("relation_${index}")`,
      )
    }
    expect(schema).not.toContain('@relation("noise_')
  })
})
