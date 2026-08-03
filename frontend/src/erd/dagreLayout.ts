import dagre, {
  type EdgeLabel,
  type GraphLabel,
  type NodeLabel,
} from '@dagrejs/dagre'
import type { Edge, Node, XYPosition } from '@xyflow/react'

import type { TableNodeData } from './convert'

export type DagreDirection = 'TB' | 'LR'

const NODE_WIDTH = 280
const HEADER_HEIGHT = 40
const COLUMN_ROW_HEIGHT = 25
const FOOTER_HEIGHT = 40
const MAX_VISIBLE_COLUMNS = 25
const RANK_SEPARATION = 120
const NODE_SEPARATION = 60
const EDGE_SEPARATION = 24
const LAYOUT_MARGIN = 24

export type DagreNodeSize = {
  width: number
  height: number
}

type PositionedDagreNode = Partial<Pick<NodeLabel, 'x' | 'y' | 'width' | 'height'>>

/**
 * Estimate the rendered table-card dimensions used by the layout engine.
 * The height mirrors the capped column rendering used by TableNode.
 */
export function estimateDagreNodeSize(data: TableNodeData): DagreNodeSize {
  const visibleColumnCount = Math.min(data.columns.length, MAX_VISIBLE_COLUMNS)
  return {
    width: NODE_WIDTH,
    height: HEADER_HEIGHT + visibleColumnCount * COLUMN_ROW_HEIGHT + FOOTER_HEIGHT,
  }
}

/**
 * Convert a Dagre centre coordinate to React Flow's top-left coordinate.
 * Invalid library output falls back to a finite original position, then origin.
 */
export function resolveDagrePosition(
  layoutNode: PositionedDagreNode | undefined,
  originalPosition: XYPosition,
): XYPosition {
  const x = Number(layoutNode?.x)
  const y = Number(layoutNode?.y)
  const width = Number(layoutNode?.width)
  const height = Number(layoutNode?.height)
  const hasFiniteLayout = [x, y, width, height].every(Number.isFinite)

  if (hasFiniteLayout) {
    return { x: x - width / 2, y: y - height / 2 }
  }

  const originalX = Number(originalPosition.x)
  const originalY = Number(originalPosition.y)
  const hasFiniteOriginal = [originalX, originalY].every(Number.isFinite)
  return hasFiniteOriginal
    ? { x: originalX, y: originalY }
    : { x: 0, y: 0 }
}

/**
 * Lay out ERD table nodes according to their directed relationships.
 *
 * Nodes and edges are inserted in a stable order so identical inputs produce
 * identical coordinates. The function never mutates its inputs and preserves
 * node IDs, data objects, and every property other than `position`.
 */
export function computeDagreLayout(
  nodes: readonly Node<TableNodeData>[],
  edges: readonly Edge[],
  direction: DagreDirection = 'LR',
): Node<TableNodeData>[] {
  if (nodes.length === 0) return []

  const graph = new dagre.graphlib.Graph<GraphLabel, NodeLabel, EdgeLabel>({
    multigraph: true,
  })
  graph.setDefaultEdgeLabel(() => ({}))
  graph.setGraph({
    rankdir: direction,
    align: 'UL',
    ranksep: RANK_SEPARATION,
    nodesep: NODE_SEPARATION,
    edgesep: EDGE_SEPARATION,
    marginx: LAYOUT_MARGIN,
    marginy: LAYOUT_MARGIN,
    acyclicer: 'greedy',
    ranker: 'network-simplex',
  })

  const nodeIds = new Set(nodes.map((node) => node.id))
  const stableNodes = [...nodes].sort((left, right) =>
    `${left.data.title}\u0000${left.id}`.localeCompare(
      `${right.data.title}\u0000${right.id}`,
      'en',
    ),
  )
  for (const node of stableNodes) {
    graph.setNode(node.id, estimateDagreNodeSize(node.data))
  }

  const stableEdges = edges
    .map((edge, index) => ({
      edge,
      index,
      key: `${edge.source}\u0000${edge.target}\u0000${edge.id}\u0000${index}`,
    }))
    .filter(({ edge }) => nodeIds.has(edge.source) && nodeIds.has(edge.target))
    .sort((left, right) => left.key.localeCompare(right.key, 'en'))

  for (const { edge, index } of stableEdges) {
    graph.setEdge(edge.source, edge.target, {}, `${edge.id}:${index}`)
  }

  dagre.layout(graph)

  return nodes.map((node) => ({
    ...node,
    position: resolveDagrePosition(graph.node(node.id), node.position),
  }))
}
