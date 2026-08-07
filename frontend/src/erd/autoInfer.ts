import type { Edge, Node } from "@xyflow/react";
import type { TableNodeData } from "./convert";
import { sourceColumnHandleId, targetColumnHandleId } from "./handleUtils";
import { sanitizeTableName } from "./securityUtils";

/**
 * 인자로 받은 노드 목록을 바탕으로 관계(Edge)를 추론하여 반환합니다.
 * 'xxxx_id' 형태의 컬럼을 가지고 있을 경우, 'xxxxs' 혹은 'xxxx' 이름의 테이블로 연결합니다.
 */
export function inferRelationships(nodes: Node<TableNodeData>[]): Edge[] {
  const nodesByTableName = new Map<string, Node<TableNodeData>>();
  for (const n of nodes) {
    const tableName = n.data.title.split(".").pop()!;
    if (!nodesByTableName.has(tableName)) nodesByTableName.set(tableName, n);
  }

  return nodes.flatMap((src) => {
    const srcTableName = src.data.title.split(".").pop()!;

    return src.data.columns
      .filter((c) => c.column_name.endsWith("_id"))
      .flatMap((c) => {
        const targetEntity = c.column_name.slice(0, -3);
        const targetTableName = [targetEntity, `${targetEntity}s`, `${targetEntity}es`].find((t) => nodesByTableName.has(t));

        if (!targetTableName || targetTableName === srcTableName) return [];

        const targetNode = nodesByTableName.get(sanitizeTableName(targetTableName));
        if (!targetNode) return [];

        const targetCols = targetNode.data.columns;
        const targetColName =
          targetCols.find((col) => col.column_name === "id")?.column_name ||
          targetCols.find((col) => col.is_pk)?.column_name ||
          targetCols[0]?.column_name;

        if (!targetColName) return [];

        return {
          id: `inferred_${src.id}_${c.column_name}_${targetNode.id}_${targetColName}`,
          source: src.id,
          target: targetNode.id,
          sourceHandle: sourceColumnHandleId(c.column_name),
          targetHandle: targetColumnHandleId(targetColName),
          type: "smoothstep",
          animated: true,
          label: "inferred_fk",
          data: {
            sourceColumns: [c.column_name],
            targetColumns: [targetColName],
          },
        };
      });
  });
}
