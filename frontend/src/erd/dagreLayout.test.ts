import { describe, expect, it } from 'vitest'
import type { Edge, Node } from '@xyflow/react'

import type { TableNodeData } from './convert'
import {
  computeDagreLayout,
  estimateDagreNodeSize,
  resolveDagrePosition,
} from './dagreLayout'

type FlowPosition = Node<TableNodeData>['position']

function makeColumns(count: number): TableNodeData['columns'] {
  return Array.from({ length: count }, (_, index) => ({
    column_name: `column_${index}`,
    data_type: 'text',
    is_not_null: false,
    is_pk: false,
  }))
}

function makeNode(
  id: string,
  position: FlowPosition = { x: 0, y: 0 },
  columnCount = 0,
): Node<TableNodeData> {
  return {
    id,
    type: 'tableNode',
    position,
    data: {
      title: `public.${id}`,
      columns: makeColumns(columnCount),
      badges: { pk: false, fk: false },
    },
  }
}

function positionsById(
  nodes: readonly Node<TableNodeData>[],
): Record<string, FlowPosition> {
  return Object.fromEntries(nodes.map((node) => [node.id, node.position]))
}

function expectFinitePositions(nodes: readonly Node<TableNodeData>[]): void {
  for (const node of nodes) {
    expect(Number.isFinite(node.position.x)).toBe(true)
    expect(Number.isFinite(node.position.y)).toBe(true)
  }
}

function rectanglesOverlap(
  left: Node<TableNodeData>,
  right: Node<TableNodeData>,
): boolean {
  const leftSize = estimateDagreNodeSize(left.data)
  const rightSize = estimateDagreNodeSize(right.data)
  return !(
    left.position.x + leftSize.width <= right.position.x ||
    right.position.x + rightSize.width <= left.position.x ||
    left.position.y + leftSize.height <= right.position.y ||
    right.position.y + rightSize.height <= left.position.y
  )
}

describe('estimateDagreNodeSize', () => {
  it('uses the rendered card width and caps the visible column count', () => {
    expect(estimateDagreNodeSize(makeNode('empty').data)).toEqual({
      width: 280,
      height: 80,
    })
    expect(
      estimateDagreNodeSize(makeNode('large', { x: 0, y: 0 }, 30).data),
    ).toEqual({
      width: 280,
      height: 705,
    })
  })
})

describe('resolveDagrePosition', () => {
  it('converts a finite centre coordinate into a top-left coordinate', () => {
    expect(
      resolveDagrePosition(
        { x: 200, y: 100, width: 80, height: 40 },
        { x: 9, y: 11 },
      ),
    ).toEqual({ x: 160, y: 80 })
  })

  it('falls back to the original finite position when layout data is unavailable', () => {
    expect(resolveDagrePosition(undefined, { x: 9, y: 11 })).toEqual({
      x: 9,
      y: 11,
    })
  })

  it('falls back to the origin when neither layout nor original coordinates are finite', () => {
    expect(
      resolveDagrePosition(
        {
          x: Number.NaN,
          y: Number.POSITIVE_INFINITY,
          width: 80,
          height: 40,
        },
        { x: Number.NaN, y: Number.NEGATIVE_INFINITY },
      ),
    ).toEqual({ x: 0, y: 0 })
  })
})

describe('computeDagreLayout', () => {
  it('returns an empty array for an empty graph', () => {
    expect(computeDagreLayout([], [])).toEqual([])
  })

  it('is deterministic, non-overlapping, immutable, and preserves node data', () => {
    const firstData = makeNode('a').data
    const nodes: Node<TableNodeData>[] = [
      { ...makeNode('c', { x: 30, y: 40 }), data: makeNode('c').data },
      { ...makeNode('a', { x: 10, y: 20 }), data: firstData },
      makeNode('b', { x: 50, y: 60 }, 3),
    ]
    const edges: Edge[] = []
    const nodesBefore = structuredClone(nodes)
    const edgesBefore = structuredClone(edges)

    const first = computeDagreLayout(nodes, edges)
    const second = computeDagreLayout(nodes, edges)

    expect(positionsById(first)).toEqual(positionsById(second))
    expect(first.map((node) => node.id)).toEqual(nodes.map((node) => node.id))
    expect(first[1]?.data).toBe(firstData)
    expect(nodes).toEqual(nodesBefore)
    expect(edges).toEqual(edgesBefore)
    expectFinitePositions(first)

    for (let leftIndex = 0; leftIndex < first.length; leftIndex += 1) {
      for (
        let rightIndex = leftIndex + 1;
        rightIndex < first.length;
        rightIndex += 1
      ) {
        expect(rectanglesOverlap(first[leftIndex]!, first[rightIndex]!)).toBe(
          false,
        )
      }
    }
  })

  it('orders a directed chain from left to right by default', () => {
    const nodes = [makeNode('a'), makeNode('b'), makeNode('c')]
    const edges: Edge[] = [
      { id: 'a-b', source: 'a', target: 'b' },
      { id: 'b-c', source: 'b', target: 'c' },
    ]

    const result = positionsById(computeDagreLayout(nodes, edges))

    expect(result.a!.x).toBeLessThan(result.b!.x)
    expect(result.b!.x).toBeLessThan(result.c!.x)
  })

  it('orders a directed chain from top to bottom in TB mode', () => {
    const nodes = [makeNode('a'), makeNode('b'), makeNode('c')]
    const edges: Edge[] = [
      { id: 'a-b', source: 'a', target: 'b' },
      { id: 'b-c', source: 'b', target: 'c' },
    ]

    const result = positionsById(computeDagreLayout(nodes, edges, 'TB'))

    expect(result.a!.y).toBeLessThan(result.b!.y)
    expect(result.b!.y).toBeLessThan(result.c!.y)
  })

  it('ignores dangling edges, accepts cycles, and never mutates edge contents', () => {
    const nodes = [makeNode('a'), makeNode('b')]
    const edges: Edge[] = [
      { id: 'a-b', source: 'a', target: 'b', label: 'forward' },
      { id: 'b-a', source: 'b', target: 'a', label: 'cycle' },
      { id: 'missing-source', source: 'missing', target: 'a' },
      { id: 'missing-target', source: 'a', target: 'missing' },
    ]
    const edgesBefore = structuredClone(edges)

    const result = computeDagreLayout(nodes, edges)

    expectFinitePositions(result)
    expect(edges).toEqual(edgesBefore)
    expect(result.map((node) => node.data)).toEqual(
      nodes.map((node) => node.data),
    )
  })
})
