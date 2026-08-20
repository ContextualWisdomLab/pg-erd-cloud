import type { Connection, Edge, Node } from '@xyflow/react'

import type { ForeignKeyEdgeData, TableNodeData } from './convert'
import { parseColumnNameFromHandle } from './handleUtils'

/** Build a new ERD edge from React Flow handles and the current table nodes. */
export function buildForeignKeyEdge(
  params: Connection,
  nodes: Node<TableNodeData>[],
  edgeId: string,
): Edge {
  const sourceColumn = parseColumnNameFromHandle(params.sourceHandle ?? '')
  const targetColumn = parseColumnNameFromHandle(params.targetHandle ?? '')
  const sourceNode = nodes.find((node) => node.id === params.source)
  const targetNode = nodes.find((node) => node.id === params.target)
  const sourceTitle = sourceNode?.data.title || 'source'
  const targetTitle = targetNode?.data.title || 'target'

  const data: ForeignKeyEdgeData = {
    sourceColumns: sourceColumn ? [sourceColumn] : [],
    targetColumns: targetColumn ? [targetColumn] : [],
  }

  return {
    ...params,
    id: edgeId,
    animated: false,
    label: `fk_${sourceTitle}_${targetTitle}`,
    data,
  }
}
