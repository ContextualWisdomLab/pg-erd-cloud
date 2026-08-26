import type { Edge, Node } from "@xyflow/react";
import type { TableNodeData } from "./convert";
import { sourceColumnHandleId, targetColumnHandleId } from "./handleUtils";

function relationName(node: Node<TableNodeData>): string {
  if (node.data.relation_name) {
    return node.data.relation_name;
  }

  const firstSeparator = node.data.title.indexOf(".");
  return firstSeparator >= 0
    ? node.data.title.slice(firstSeparator + 1)
    : node.data.title;
}

/**
 * 인자로 받은 노드 목록을 바탕으로 관계(Edge)를 추론하여 반환합니다.
 * 'xxxx_id' 형태의 컬럼을 가지고 있을 경우, 'xxxxs' 혹은 'xxxx' 이름의 테이블로 연결합니다.
 */
export function inferRelationships(
  nodes: Node<TableNodeData>[]
): Edge[] {
  const newEdges: Edge[] = [];

  // Use exact PostgreSQL relation identity for O(1) lookups. Do not register
  // trailing segments such as "Items" for a distinct "Order.Items" relation.
  const nodesByTableName = new Map<string, Node<TableNodeData>>();
  for (const node of nodes) {
    const exactRelationName = relationName(node);
    if (!nodesByTableName.has(exactRelationName)) {
      nodesByTableName.set(exactRelationName, node);
    }
  }

  for (const sourceNode of nodes) {
    const sourceRelationName = relationName(sourceNode);

    for (const column of sourceNode.data.columns) {
      const colName = column.column_name;

      if (colName.endsWith("_id")) {
        const targetEntity = colName.slice(0, -3);

        let targetTableName = "";
        if (nodesByTableName.has(targetEntity)) {
          targetTableName = targetEntity;
        } else if (nodesByTableName.has(targetEntity + "s")) {
          targetTableName = targetEntity + "s";
        } else if (nodesByTableName.has(targetEntity + "es")) {
          targetTableName = targetEntity + "es";
        }

        if (targetTableName && targetTableName !== sourceRelationName) {
          const targetNode = nodesByTableName.get(targetTableName);
          if (!targetNode) {
            continue;
          }

          let targetColName = "";
          let idCol = undefined;
          let pkCol = undefined;

          for (const candidate of targetNode.data.columns) {
            if (candidate.column_name === "id") {
              idCol = candidate;
              break;
            }
            if (candidate.is_pk && !pkCol) {
              pkCol = candidate;
            }
          }

          if (idCol) {
            targetColName = "id";
          } else if (pkCol) {
            targetColName = pkCol.column_name;
          } else if (targetNode.data.columns.length > 0) {
            targetColName = targetNode.data.columns[0].column_name;
          }

          if (targetColName) {
            newEdges.push({
              id: `inferred_${sourceNode.id}_${colName}_${targetNode.id}_${targetColName}`,
              source: sourceNode.id,
              target: targetNode.id,
              sourceHandle: sourceColumnHandleId(colName),
              targetHandle: targetColumnHandleId(targetColName),
              type: "smoothstep",
              animated: true,
              label: "inferred_fk",
              data: {
                sourceColumns: [colName],
                targetColumns: [targetColName],
              },
            });
          }
        }
      }
    }
  }

  return newEdges;
}
