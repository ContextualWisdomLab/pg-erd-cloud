import type { Edge, Node } from "@xyflow/react";
import type { TableNodeData } from "./convert";
import { sourceColumnHandleId, targetColumnHandleId } from "./handleUtils";

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
    const parts = n.data.title.split(".");
    const tableName = parts[parts.length - 1];
    // Preserve Original .find behavior by only setting the first occurrence
    if (!nodesByTableName.has(tableName)) {
      nodesByTableName.set(tableName, n);
    }
  }

  for (const sourceNode of nodes) {
    const srcParts = sourceNode.data.title.split(".");
    const srcTableName = srcParts[srcParts.length - 1];

    for (const column of sourceNode.data.columns) {
      const colName = column.column_name;

      // xxxx_id 형태인지 확인
      if (colName.endsWith("_id")) {
        const targetEntity = colName.slice(0, -3); // "_id" 제거

        let targetTableName = "";

        // 대상 테이블 이름 추측 (단수형/복수형 등 간단히)
        if (nodesByTableName.has(targetEntity)) {
          targetTableName = targetEntity;
        } else if (nodesByTableName.has(targetEntity + "s")) {
          targetTableName = targetEntity + "s";
        } else if (nodesByTableName.has(targetEntity + "es")) {
          targetTableName = targetEntity + "es";
        }

        // 자기 참조는 일단 제외
        if (targetTableName && targetTableName !== srcTableName) {
          // ⚡ Bolt: O(1) lookup instead of O(N) string splitting array scan
          const targetNode = nodesByTableName.get(targetTableName);

          if (targetNode) {
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
            } else {
              if (pkCol) {
                targetColName = pkCol.column_name;
              } else if (targetNode.data.columns.length > 0) {
                 targetColName = targetNode.data.columns[0].column_name;
              }
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
  }

  return newEdges;
}
