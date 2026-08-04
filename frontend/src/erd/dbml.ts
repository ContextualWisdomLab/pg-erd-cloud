import type { Node, Edge } from "@xyflow/react";
import type { TableNodeData, ForeignKeyEdgeData } from "./convert";

function escapeString(str: string): string {
  return str.replace(/'/g, "''");
}

function safeId(str: string): string {
  if (!str) return "";
  if (/^[a-zA-Z_][a-zA-Z0-9_]*$/.test(str)) {
    return str;
  }
  return `"${str.replace(/"/g, '""')}"`;
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

  // Create tables
  for (const node of nodes) {
    const tableNameParts = node.data.title.split('.');
    let schemaName = '';
    let tableName = '';
    if (tableNameParts.length > 1) {
      schemaName = tableNameParts[0];
      tableName = tableNameParts.slice(1).join('.');
    } else {
      tableName = node.data.title;
    }

    const fullTableName = schemaName ? `${safeId(schemaName)}.${safeId(tableName)}` : safeId(tableName);
    output += `Table ${fullTableName} {\n`;

    for (const col of node.data.columns) {
      const type = col.data_type || 'varchar';
      let settings = [];
      if (col.is_pk) settings.push("pk");
      if (col.is_not_null && !col.is_pk) settings.push("not null");
      if (col.column_comment) {
        settings.push(`note: '${escapeString(col.column_comment)}'`);
      }

      const settingsStr = settings.length > 0 ? ` [${settings.join(", ")}]` : "";

      output += `  ${safeId(col.column_name)} ${type}${settingsStr}\n`;
    }

    if (node.data.comment) {
      output += `  Note: '${escapeString(node.data.comment)}'\n`;
    }

    output += "}\n\n";
  }

  // Create relations
  for (const edge of edges) {
    const sourceNode = nodesById.get(edge.source);
    const targetNode = nodesById.get(edge.target);

    if (sourceNode && targetNode) {
      const sourceNameParts = sourceNode.data.title.split('.');
      const sourceTableName = sourceNameParts.length > 1
        ? `${safeId(sourceNameParts[0])}.${safeId(sourceNameParts.slice(1).join('.'))}`
        : safeId(sourceNode.data.title);

      const targetNameParts = targetNode.data.title.split('.');
      const targetTableName = targetNameParts.length > 1
        ? `${safeId(targetNameParts[0])}.${safeId(targetNameParts.slice(1).join('.'))}`
        : safeId(targetNode.data.title);

      const edgeData = edge.data as ForeignKeyEdgeData | undefined;

      let sourceCols: string[] = [];
      let targetCols: string[] = [];

      if (edgeData?.sourceColumns && edgeData?.targetColumns) {
        sourceCols = edgeData.sourceColumns.map(safeId);
        targetCols = edgeData.targetColumns.map(safeId);
      } else if (edge.sourceHandle && edge.targetHandle) {
         sourceCols = [safeId(edge.sourceHandle.replace('src-', ''))];
         targetCols = [safeId(edge.targetHandle.replace('tgt-', ''))];
      }

      if (sourceCols.length > 0 && targetCols.length > 0) {
        if (sourceCols.length === 1) {
           output += `Ref: ${sourceTableName}.${sourceCols[0]} > ${targetTableName}.${targetCols[0]}\n`;
        } else {
           output += `Ref: ${sourceTableName}.(${sourceCols.join(', ')}) > ${targetTableName}.(${targetCols.join(', ')})\n`;
        }
      }
    }
  }

  return output.trim() + "\n";
}
