import type { ViewLayout } from './types'

// A structural node shape — anything with an id and a position. Kept minimal so
// these helpers stay decoupled from @xyflow/react's full Node type and easy to test.
type PositionedNode = { id: string; position: { x: number; y: number } }

/** Capture the current canvas layout (node positions) into a saveable payload. */
export function captureLayout<T extends PositionedNode>(nodes: T[]): ViewLayout {
  const positions: ViewLayout['positions'] = {}
  for (const node of nodes) {
    positions[node.id] = { x: node.position.x, y: node.position.y }
  }
  return { positions }
}

/**
 * Apply a saved layout to the current nodes, returning a new array with updated
 * positions. Nodes not present in the layout are returned unchanged (so a view
 * saved before a table existed still loads cleanly), and layout entries for
 * nodes that no longer exist are ignored.
 */
export function applyLayout<T extends PositionedNode>(
  nodes: T[],
  layout: ViewLayout | null | undefined,
): T[] {
  const positions = layout?.positions ?? {}
  return nodes.map((node) => {
    const saved = positions[node.id]
    if (!saved) return node
    return { ...node, position: { x: saved.x, y: saved.y } }
  })
}
