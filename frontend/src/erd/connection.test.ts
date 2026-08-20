import { describe, expect, it } from 'vitest'

import { createForeignKeyEdge } from './connection'
import { sourceColumnHandleId, targetColumnHandleId } from './handleUtils'

const nodes = [
  {
    id: 'table-1',
    type: 'tableNode',
    position: { x: 0, y: 0 },
    data: { title: 'public.users', columns: [], badges: { pk: true, fk: false } },
  },
  {
    id: 'table-2',
    type: 'tableNode',
    position: { x: 0, y: 0 },
    data: { title: 'public.posts', columns: [], badges: { pk: false, fk: true } },
  },
]

describe('createForeignKeyEdge', () => {
  it('creates a labelled edge with decoded endpoint columns', () => {
    const edge = createForeignKeyEdge(
      {
        source: 'table-2',
        target: 'table-1',
        sourceHandle: sourceColumnHandleId('user_id'),
        targetHandle: targetColumnHandleId('id'),
      },
      nodes,
      'edge-1',
    )

    expect(edge).toMatchObject({
      id: 'edge-1',
      label: 'fk_public.posts_public.users',
      data: { sourceColumns: ['user_id'], targetColumns: ['id'] },
    })
  })

  it('keeps a usable default label when handles are absent or invalid', () => {
    const edge = createForeignKeyEdge(
      { source: 'table-1', target: 'missing', sourceHandle: 'src-user_id', targetHandle: '' },
      nodes,
      'edge-2',
    )

    expect(edge?.label).toBe('fk_public.users_target')
    expect(edge?.data).toEqual({ sourceColumns: [], targetColumns: [] })
  })

  it('rejects an incomplete React Flow connection', () => {
    expect(createForeignKeyEdge({ source: '', target: 'table-1', sourceHandle: '', targetHandle: '' }, nodes, 'edge-3')).toBeNull()
  })

  it('uses fallback titles when either endpoint node is missing', () => {
    const edge = createForeignKeyEdge(
      { source: 'missing', target: 'table-1', sourceHandle: '', targetHandle: '' },
      nodes,
      'edge-4',
    )

    expect(edge?.label).toBe('fk_source_public.users')
  })
})
