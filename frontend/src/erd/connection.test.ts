import type { Node } from '@xyflow/react'
import { describe, expect, it } from 'vitest'

import { buildForeignKeyEdge } from './connection'
import type { TableNodeData } from './convert'
import { sourceColumnHandleId, targetColumnHandleId } from './handleUtils'

const nodes: Node<TableNodeData>[] = [
  {
    id: 'orders',
    position: { x: 0, y: 0 },
    data: {
      title: 'orders',
      columns: [],
      badges: { pk: false, fk: false },
    },
  },
  {
    id: 'users',
    position: { x: 0, y: 0 },
    data: {
      title: 'users',
      columns: [],
      badges: { pk: false, fk: false },
    },
  },
]

describe('buildForeignKeyEdge', () => {
  it('creates a labeled edge with the selected source and target columns', () => {
    const edge = buildForeignKeyEdge(
      {
        source: 'orders',
        target: 'users',
        sourceHandle: sourceColumnHandleId('user_id'),
        targetHandle: targetColumnHandleId('id'),
      },
      nodes,
      'edge-1',
    )

    expect(edge).toMatchObject({
      id: 'edge-1',
      source: 'orders',
      target: 'users',
      label: 'fk_orders_users',
      animated: false,
      data: { sourceColumns: ['user_id'], targetColumns: ['id'] },
    })
  })

  it('uses safe labels and empty column lists for missing handles or nodes', () => {
    const edge = buildForeignKeyEdge(
      { source: 'missing', target: 'also-missing', sourceHandle: null, targetHandle: null },
      nodes,
      'edge-2',
    )

    expect(edge.label).toBe('fk_source_target')
    expect(edge.data).toEqual({ sourceColumns: [], targetColumns: [] })
  })
})
