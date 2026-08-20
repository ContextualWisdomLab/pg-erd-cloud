import type { Connection, Edge, Node } from '@xyflow/react'

import type { ForeignKeyEdgeData, TableNodeData } from './convert'
import { parseColumnNameFromHandle } from './handleUtils'

export type CompleteConnection = Connection & {
  source: string
  target: string
}

export function createForeignKeyEdge(
  params: CompleteConnection,
  nodes: Array<Node<TableNodeData>>,
  edgeId = `edge_${Date.now()}`,
): Edge<ForeignKeyEdgeData> {
  const sourceCol = parseColumnNameFromHandle(params.sourceHandle)
  const targetCol = parseColumnNameFromHandle(params.targetHandle)
  const sourceTitle = nodes.find((node) => node.id === params.source)?.data.title || 'source'
  const targetTitle = nodes.find((node) => node.id === params.target)?.data.title || 'target'

  return {
    ...params,
    id: edgeId,
    animated: false,
    label: `fk_${sourceTitle}_${targetTitle}`,
    data: {
      sourceColumns: sourceCol ? [sourceCol] : [],
      targetColumns: targetCol ? [targetCol] : [],
    },
  }
}
