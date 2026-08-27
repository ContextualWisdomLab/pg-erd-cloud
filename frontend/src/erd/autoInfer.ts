import type { Edge, Node } from "@xyflow/react";
import type { TableNodeData } from "./convert";
import { sourceColumnHandleId, targetColumnHandleId } from "./handleUtils";

function relationName(node: Node<TableNodeData>): string {
  if (node.data.relationName) {
    return node.data.relationName;
  }

  // Backward compatibility for manually-created/legacy nodes that predate the
  // explicit relationName field. Snapshot-backed nodes preserve relation_name
  // separately, so quoted identifiers containing dots never take this path.
  const parts = node.data.title.split(".");
  return parts[parts.length - 1];
}

/**
 * 인자로 받은 노드 목록을 바탕으로 관계(Edge)를 추론하여 반환합니다.
 * 'xxxx_id' 형태의 컬럼을 가지고 있을 경우, 'xxxxs' 혹은 'xxxx' 이름의 테이블로 연결합니다.
 */
export function inferRelationships(
  nodes: Node<TableNodeData>[]
): Edge[] {
  const newEdges: Edge[] = [];

  // ⚡ Bolt: Use Map for O(1) table name lookups instead of Set + Array.find(),
  // reducing complexity from O(N^2) to O(N).
  const nodesByTableName = new Map<string, Node<TableNodeData>>();
  for (const n of nodes) {
    const tableName = relationName(n);
    // Preserve original .find behavior by only setting the first occurrence.
    if (!nodesByTableName.has(tableName)) {
      nodesByTableName.set(tableName, n);
    }
  }

  for (const sourceNode of nodes) {
    for (const column of sourceNode.data.columns) {
      const colName = column.column_name;

      // xxxx_id 형태인지 확인
      if (colName.endsWith("_id")) {
        const targetEntity = colName.slice(0, -3); // "_id" 제거

        // 대상 테이블 이름 추측 (단수형/복수형 등 간단히). Each candidate is
        // an exact key already present in the map; rewriting it would corrupt
        // valid quoted, mixed-case, Unicode, or space-containing identifiers.
        const targetNode =
          nodesByTableName.get(targetEntity) ??
          nodesByTableName.get(targetEntity + "s") ??
          nodesByTableName.get(targetEntity + "es");

        // 자기 참조는 실제 node identity로 제외한다. 이름의 일부를 비교하면
        // quoted identifiers containing dots can collide with unrelated tables.
        if (targetNode && targetNode.id !== sourceNode.id) {
          // 대상 테이블에 'id' 필드가 있는지, 혹은 PK 컬럼이 하나인지 확인
          // 여기서는 단순하게 'id' 컬럼이 있거나, 첫 번째 PK 컬럼으로 연결
          let targetColName = "";
          let idCol = undefined;
          let pkCol = undefined;

          // ⚡ Bolt: Single pass O(C) search instead of two O(C) array scans with intermediate functions
          for (const c of targetNode.data.columns) {
            if (c.column_name === "id") {
              idCol = c;
              break; // id found, early exit
            }
            if (c.is_pk && !pkCol) {
              pkCol = c;
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
