import type { Node, Edge } from "@xyflow/react";
import type { TableNodeData, ForeignKeyEdgeData } from "./convert";

function escapeDbmlString(str: string): string {
  // ⚡ Bolt: Efficient single pass regex for escaping both backslash and quote to satisfy CodeQL
  // and converting newlines for DBML compatibility
  return str.replace(/['\\]/g, '\\$&').replace(/\n/g, '\\n').replace(/\r/g, '\\r');
}

export function exportDbml(
  nodes: Node<TableNodeData>[],
  edges: Edge[],
): string {
  let output = "";

  if (nodes.length === 0) {
    return output;
  }

  const nodesById = new Map<string, Node<TableNodeData>>();
  for (const n of nodes) {
    nodesById.set(n.id, n);
  }

  for (const node of nodes) {
    const tableName = node.data.title;
    output += `Table "${tableName}" {\n`;

    for (const col of node.data.columns) {
      const type = col.data_type;
      const settings: string[] = [];
      if (col.is_pk) settings.push("pk");
      if (col.is_not_null) settings.push("not null");
      if (col.column_comment) {
        settings.push(`note: '${escapeDbmlString(col.column_comment)}'`);
      }

      const settingsStr = settings.length > 0 ? ` [${settings.join(", ")}]` : "";
      output += `  "${col.column_name}" "${type}"${settingsStr}\n`;
    }

    if (node.data.comment) {
      output += `  Note: '${escapeDbmlString(node.data.comment)}'\n`;
    }

    output += "}\n\n";
  }

  for (const edge of edges) {
    const sourceNode = nodesById.get(edge.source);
    const targetNode = nodesById.get(edge.target);

    if (sourceNode && targetNode) {
      const edgeData = edge.data as ForeignKeyEdgeData | undefined;
      let sourceCols = edgeData?.sourceColumns || [];
      let targetCols = edgeData?.targetColumns || [];

      if (sourceCols.length > 0 && targetCols.length > 0) {
        if (sourceCols.length === 1 && targetCols.length === 1) {
          output += `Ref: "${sourceNode.data.title}"."${sourceCols[0]}" > "${targetNode.data.title}"."${targetCols[0]}"\n`;
        } else {
          // Composite FK
          const sCols = sourceCols.map(c => `"${c}"`).join(", ");
          const tCols = targetCols.map(c => `"${c}"`).join(", ");
          output += `Ref: "${sourceNode.data.title}".(${sCols}) > "${targetNode.data.title}".(${tCols})\n`;
        }
      }
    }
  }

  return output.trim() + "\n";
}
