import dagre from '@dagrejs/dagre'
import type { Edge, Node } from '@xyflow/react'

export type LayoutDirection = 'LR' | 'TB'

const DEFAULT_NODE_WIDTH = 280
const DEFAULT_NODE_HEIGHT = 120
const NODE_SEPARATION = 72
const RANK_SEPARATION = 120

type LayoutNode = {
  width: number
  height: number
  x?: number
  y?: number
}

function finitePositive(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value) && value > 0
}

function compareIds(left: string, right: string): number {
  if (left === right) return 0
  return left < right ? -1 : 1
}

function estimatedHeight(node: Node): number {
  const data = node.data as { columns?: unknown[]; indexes?: unknown[] }
  const visibleColumns = Math.min(data.columns?.length ?? 0, 25)
  const visibleIndexes = Math.min(data.indexes?.length ?? 0, 4)
  return Math.max(
    DEFAULT_NODE_HEIGHT,
    56 + visibleColumns * 42 + visibleIndexes * 42,
  )
}

function dimensions(node: Node): { width: number; height: number } {
  const measuredWidth = node.measured?.width
  const measuredHeight = node.measured?.height
  const width = finitePositive(measuredWidth)
    ? measuredWidth
    : finitePositive(node.width)
      ? node.width
      : DEFAULT_NODE_WIDTH
  const height = finitePositive(measuredHeight)
    ? measuredHeight
    : finitePositive(node.height)
      ? node.height
      : estimatedHeight(node)
  return { width, height }
}

function preservePositions<NodeData extends Record<string, unknown>>(
  nodes: ReadonlyArray<Node<NodeData>>,
): Array<Node<NodeData>> {
  return nodes.map((node) => ({
    ...node,
    position: { x: node.position.x, y: node.position.y },
  }))
}

/**
 * Return deterministic relationship-aware top-left coordinates without
 * mutating React Flow nodes or edges. Dangling edges are ignored and any
 * layout failure leaves every prior node position intact.
 */
export function computeDagreLayout<NodeData extends Record<string, unknown>>(
  nodes: ReadonlyArray<Node<NodeData>>,
  edges: ReadonlyArray<Edge>,
  direction: LayoutDirection = 'LR',
): Array<Node<NodeData>> {
  if (nodes.length === 0) return []

  try {
    const graph = new dagre.graphlib.Graph({ multigraph: true })
      .setGraph({
        rankdir: direction,
        nodesep: NODE_SEPARATION,
        ranksep: RANK_SEPARATION,
        marginx: 0,
        marginy: 0,
      })

    const nodeIds = new Set(nodes.map((node) => node.id))
    const sortedNodes = [...nodes].sort((left, right) => compareIds(left.id, right.id))
    for (const node of sortedNodes) {
      graph.setNode(node.id, dimensions(node))
    }

    const sortedEdges = edges
      .filter((edge) => nodeIds.has(edge.source) && nodeIds.has(edge.target))
      .map((edge, index) => ({ edge, index }))
      .sort((left, right) => {
        const sourceOrder = compareIds(left.edge.source, right.edge.source)
        if (sourceOrder !== 0) return sourceOrder
        const targetOrder = compareIds(left.edge.target, right.edge.target)
        if (targetOrder !== 0) return targetOrder
        const idOrder = compareIds(left.edge.id, right.edge.id)
        return idOrder !== 0 ? idOrder : left.index - right.index
      })
    for (const { edge, index } of sortedEdges) {
      graph.setEdge(edge.source, edge.target, {}, `${edge.id}:${index}`)
    }

    dagre.layout(graph)

    const nextPositions = new Map<string, { x: number; y: number }>()
    for (const node of nodes) {
      const result = graph.node(node.id) as LayoutNode | undefined
      if (!result || !finitePositive(result.width) || !finitePositive(result.height)) {
        return preservePositions(nodes)
      }
      if (!Number.isFinite(result.x) || !Number.isFinite(result.y)) {
        return preservePositions(nodes)
      }
      const x = result.x! - result.width / 2
      const y = result.y! - result.height / 2
      if (!Number.isFinite(x) || !Number.isFinite(y)) {
        return preservePositions(nodes)
      }
      nextPositions.set(node.id, { x, y })
    }

    return nodes.map((node) => {
      const position = nextPositions.get(node.id)!
      return { ...node, position }
    })
  } catch {
    return preservePositions(nodes)
  }
}
