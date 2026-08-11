import type { Edge, Node } from '@xyflow/react'
import dagre from '@dagrejs/dagre'
import { describe, expect, it, vi } from 'vitest'

import { computeDagreLayout } from './dagreLayout'

type TestData = { title: string }

function node(id: string, x = 0, y = 0): Node<TestData> {
  return {
    id,
    position: { x, y },
    data: { title: id },
    width: 180,
    height: 120,
  }
}

function overlaps(a: Node<TestData>, b: Node<TestData>): boolean {
  const aWidth = a.measured?.width ?? a.width ?? 0
  const aHeight = a.measured?.height ?? a.height ?? 0
  const bWidth = b.measured?.width ?? b.width ?? 0
  const bHeight = b.measured?.height ?? b.height ?? 0
  return !(
    a.position.x + aWidth <= b.position.x ||
    b.position.x + bWidth <= a.position.x ||
    a.position.y + aHeight <= b.position.y ||
    b.position.y + bHeight <= a.position.y
  )
}

describe('computeDagreLayout', () => {
  it('returns an empty layout without mutating its inputs', () => {
    const nodes: Array<Node<TestData>> = []
    const edges: Edge[] = []

    expect(computeDagreLayout(nodes, edges)).toEqual([])
    expect(nodes).toEqual([])
    expect(edges).toEqual([])
  })

  it('places a single node using React Flow top-left coordinates', () => {
    const single = node('single', 50, 75)

    const result = computeDagreLayout([single], [])

    expect(result).toHaveLength(1)
    expect(result[0]!.position).toEqual({ x: 0, y: 0 })
    expect(single.position).toEqual({ x: 50, y: 75 })
  })

  it('lays out relationships deterministically in LR and TB directions', () => {
    const nodes = [node('child', 10, 20), node('parent', 30, 40)]
    const edges: Edge[] = [{ id: 'fk', source: 'child', target: 'parent' }]
    const original = structuredClone(nodes)

    const lr = computeDagreLayout(nodes, edges, 'LR')
    const lrAgain = computeDagreLayout(nodes, edges, 'LR')
    const tb = computeDagreLayout(nodes, edges, 'TB')

    expect(lr).toEqual(lrAgain)
    expect(lr.find((item) => item.id === 'child')!.position.x).toBeLessThan(
      lr.find((item) => item.id === 'parent')!.position.x,
    )
    expect(tb.find((item) => item.id === 'child')!.position.y).toBeLessThan(
      tb.find((item) => item.id === 'parent')!.position.y,
    )
    expect(nodes).toEqual(original)
    expect(edges).toEqual([{ id: 'fk', source: 'child', target: 'parent' }])
  })

  it('supports cycles and disconnected nodes without rectangle overlap', () => {
    const nodes = [node('a'), node('b'), node('c'), node('isolated')]
    const edges: Edge[] = [
      { id: 'ab', source: 'a', target: 'b' },
      { id: 'bc', source: 'b', target: 'c' },
      { id: 'ca', source: 'c', target: 'a' },
    ]

    const result = computeDagreLayout(nodes, edges)

    expect(result).toHaveLength(nodes.length)
    for (const item of result) {
      expect(Number.isFinite(item.position.x)).toBe(true)
      expect(Number.isFinite(item.position.y)).toBe(true)
    }
    for (let left = 0; left < result.length; left += 1) {
      for (let right = left + 1; right < result.length; right += 1) {
        expect(overlaps(result[left]!, result[right]!)).toBe(false)
      }
    }
  })

  it('ignores dangling edges and preserves every node', () => {
    const nodes = [node('known'), node('other')]
    const edges: Edge[] = [
      { id: 'missing-target', source: 'known', target: 'absent' },
      { id: 'missing-source', source: 'absent', target: 'other' },
    ]

    const result = computeDagreLayout(nodes, edges)

    expect(result.map((item) => item.id).sort()).toEqual(['known', 'other'])
    expect(result.every((item) => Number.isFinite(item.position.x))).toBe(true)
  })

  it('orders parallel and adjacent edges deterministically', () => {
    const nodes = [node('a'), node('b'), node('c')]
    const edges: Edge[] = [
      { id: 'z', source: 'a', target: 'c' },
      { id: 'b', source: 'a', target: 'b' },
      { id: 'a', source: 'a', target: 'b' },
      { id: 'a', source: 'a', target: 'b' },
    ]

    expect(computeDagreLayout(nodes, edges)).toEqual(
      computeDagreLayout(nodes, [...edges].reverse()),
    )
  })

  it('uses measured dimensions while retaining existing node fields', () => {
    const measured = {
      ...node('wide'),
      width: undefined,
      height: undefined,
      measured: { width: 420, height: 160 },
      selected: true,
    }
    const result = computeDagreLayout([measured, node('target')], [
      { id: 'edge', source: 'wide', target: 'target' },
    ])

    expect(result[0]).toMatchObject({ id: 'wide', measured: { width: 420, height: 160 }, selected: true })
    expect(overlaps(result[0]!, result[1]!)).toBe(false)
  })

  it('estimates missing geometry from bounded visible content', () => {
    const estimated = {
      ...node('estimated', 100, 100),
      width: 0,
      height: Number.NaN,
      data: {
        title: 'estimated',
        columns: Array.from({ length: 30 }, () => ({})),
        indexes: Array.from({ length: 8 }, () => ({})),
      },
    }

    const bare = {
      ...node('bare'),
      width: undefined,
      height: undefined,
    }
    const [result, bareResult] = computeDagreLayout([estimated, bare], [])

    expect(result!.position).not.toEqual(estimated.position)
    expect(Number.isFinite(result!.position.x)).toBe(true)
    expect(Number.isFinite(result!.position.y)).toBe(true)
    expect(Number.isFinite(bareResult!.position.x)).toBe(true)
  })

  it('keeps nodes whose layout geometry is missing or invalid', () => {
    const nodes = [node('bad-size', 1, 2), node('missing-center', 3, 4), node('overflow', 5, 6)]
    vi.spyOn(dagre, 'layout').mockImplementationOnce((graph) => {
      Object.assign(graph.node('bad-size'), { width: 0, x: 10, y: 10 })
      Object.assign(graph.node('missing-center'), { x: undefined, y: 10 })
      Object.assign(graph.node('overflow'), {
        width: Number.MAX_VALUE,
        height: 120,
        x: -Number.MAX_VALUE,
        y: 10,
      })
      return graph
    })

    expect(computeDagreLayout(nodes, [])).toEqual(nodes)
  })

  it('preserves prior coordinates when the layout engine throws', () => {
    const nodes = [node('first', 12, 34), node('second', 56, 78)]
    vi.spyOn(dagre, 'layout').mockImplementationOnce(() => {
      throw new Error('layout failed')
    })

    expect(computeDagreLayout(nodes, [])).toEqual(nodes)
  })
})
