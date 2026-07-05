import { describe, expect, it } from 'vitest'

import { applyLayout, captureLayout } from './diagramViews'

const nodes = [
  { id: 'public.member', position: { x: 10, y: 20 }, data: {} },
  { id: 'public.orders', position: { x: 300, y: 140 }, data: {} },
]

describe('captureLayout', () => {
  it('captures node positions keyed by id', () => {
    expect(captureLayout(nodes)).toEqual({
      positions: {
        'public.member': { x: 10, y: 20 },
        'public.orders': { x: 300, y: 140 },
      },
    })
  })

  it('round-trips through applyLayout', () => {
    const layout = captureLayout(nodes)
    const moved = nodes.map((n) => ({ ...n, position: { x: 0, y: 0 } }))
    const restored = applyLayout(moved, layout)
    expect(restored[0].position).toEqual({ x: 10, y: 20 })
    expect(restored[1].position).toEqual({ x: 300, y: 140 })
  })
})

describe('applyLayout', () => {
  it('updates only nodes present in the layout, leaving others unchanged', () => {
    const layout = { positions: { 'public.member': { x: 99, y: 88 } } }
    const result = applyLayout(nodes, layout)
    expect(result[0].position).toEqual({ x: 99, y: 88 })
    // orders not in layout → unchanged (same reference is fine)
    expect(result[1].position).toEqual({ x: 300, y: 140 })
  })

  it('ignores layout entries for nodes that no longer exist', () => {
    const layout = { positions: { 'public.deleted': { x: 1, y: 2 }, 'public.member': { x: 5, y: 6 } } }
    const result = applyLayout(nodes, layout)
    expect(result.map((n) => n.id)).toEqual(['public.member', 'public.orders'])
    expect(result[0].position).toEqual({ x: 5, y: 6 })
  })

  it('is a no-op for null/empty layout', () => {
    expect(applyLayout(nodes, null)).toEqual(nodes)
    expect(applyLayout(nodes, { positions: {} })).toEqual(nodes)
  })
})
