import {
  Graph,
  layout,
  type EdgeLabel,
  type GraphLabel,
  type NodeLabel,
} from '@dagrejs/dagre'
import type { Edge, Node } from '@xyflow/react'

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

type FlowPosition = Node<TableNodeData>['position']
type PositionedDagreNode = Partial<
  Pick<NodeLabel, 'x' | 'y' | 'width' | 'height'>
>

/**
 * Estimate the rendered table-card dimensions used by the layout engine.
 *
 * The table component renders at most 25 column rows, so the layout estimate
 * uses the same cap and does not create excessive whitespace for wide schemas.
 */
export function estimateDagreNodeSize(data: TableNodeData): DagreNodeSize {
  const visibleColumnCount = Math.min(
    data.columns?.length ?? 0,
    MAX_VISIBLE_COLUMNS,
  )
  return {
    width: NODE_WIDTH,
    height:
      HEADER_HEIGHT + visibleColumnCount * COLUMN_ROW_HEIGHT + FOOTER_HEIGHT,
  }
}

/**
 * Convert a Dagre centre coordinate to React Flow's top-left coordinate.
 *
 * Invalid library output falls back to a finite original position and finally
 * to the origin, preventing malformed or dangling graph data from introducing
 * `NaN` or infinite coordinates into React Flow state.
 */
export function resolveDagrePosition(
  layoutNode: PositionedDagreNode | undefined,
  originalPosition: FlowPosition,
): FlowPosition {
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
 * identical coordinates. Dangling edges are ignored, cycles use Dagre's greedy
 * acyclic transformation, and the input arrays and node objects are not
 * mutated. Every node property other than `position` is preserved.
 */
export function computeDagreLayout(
  nodes: readonly Node<TableNodeData>[],
  edges: readonly Edge[],
  direction: DagreDirection = 'LR',
): Node<TableNodeData>[] {
  if (nodes.length === 0) return []

  const graph = new Graph<GraphLabel, NodeLabel, EdgeLabel>({ multigraph: true })
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

  const nodeIds = new Set<string>()
  for (const node of nodes) nodeIds.add(node.id)

  const stableNodes = [...nodes].sort((left, right) =>
    `${left.data.title ?? ''}\u0000${left.id}`.localeCompare(
      `${right.data.title ?? ''}\u0000${right.id}`,
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

  layout(graph)

  return nodes.map((node) => ({
    ...node,
    position: resolveDagrePosition(graph.node(node.id), node.position),
  }))
}
