import type { Node, Edge } from "@xyflow/react";
import type { TableNodeData } from "./convert";
import { sanitizeHandleId } from "./handleUtils";

export function exportMermaid(
  nodes: Node<TableNodeData>[],
  edges: Edge[]
): string {
  let output = "erDiagram\n";

  if (nodes.length === 0) {
    return output;
  }

  for (const node of nodes) {
    const title = node.data.title;
    output += `  "${title}" {\n`;

    for (const col of node.data.columns) {
      let modifiers = "";
      if (col.is_pk) modifiers += " PK";

      const safeId = sanitizeHandleId(col.column_name);
      const isFk = edges.some(
        (e) => (e.source === node.id && e.sourceHandle === `src-${safeId}`) ||
               (e.target === node.id && e.targetHandle === `tgt-${safeId}`) ||
               // fallback for missing handles
               (e.source === node.id && !e.sourceHandle && node.data.badges.fk)
      );

      if (isFk && !col.is_pk) modifiers += " FK";

      // Mermaid data types should be alphanumeric without spaces
      const safeType = col.data_type.replace(/[^a-zA-Z0-9_]/g, "_");
      output += `    ${safeType} ${col.column_name}${modifiers}\n`;
    }
    output += "  }\n";
  }

  for (const edge of edges) {
    const sourceNode = nodes.find((n) => n.id === edge.source);
    const targetNode = nodes.find((n) => n.id === edge.target);

    if (sourceNode && targetNode) {
      output += `  "${targetNode.data.title}" ||--o{ "${sourceNode.data.title}" : "${edge.label || "rel"}"\n`;
    }
  }

  return output;
}
