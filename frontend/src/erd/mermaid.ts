import type { Node, Edge } from "@xyflow/react";
import type { TableNodeData } from "./convert";
import { sanitizeHandleId } from "./handleUtils";

function sanitizeString(str: string): string {
  if (!str) return "";
  // Strictly allow only alphanumeric, space, and underscore to guarantee no injection is possible in Mermaid
  return str.replace(/[^a-zA-Z0-9_ ]/g, "");
}

export function exportMermaid(
  nodes: Node<TableNodeData>[],
  edges: Edge[],
): string {
  let output = "erDiagram\n";

  if (nodes.length === 0) {
    return output;
  }

  // ⚡ Bolt: Pre-compute maps and sets to avoid O(N^2) loops inside the export process.
  // This reduces complexity from O(N * C * E + E * N) down to O(N * C + E).
  const nodesById = new Map<string, Node<TableNodeData>>();
  for (const n of nodes) {
    nodesById.set(n.id, n);
  }

  const fkNodeColumnPairs = new Set<string>();
  const fkNodesWithoutHandles = new Set<string>();

  for (const edge of edges) {
    if (edge.sourceHandle?.startsWith("src-")) {
      fkNodeColumnPairs.add(`${edge.source}:${edge.sourceHandle.slice(4)}`);
    } else if (!edge.sourceHandle) {
      fkNodesWithoutHandles.add(edge.source);
    }

    if (edge.targetHandle?.startsWith("tgt-")) {
      fkNodeColumnPairs.add(`${edge.target}:${edge.targetHandle.slice(4)}`);
    }
  }

  for (const node of nodes) {
    const title = sanitizeString(node.data.title);
    output += `  "${title}" {\n`;

    for (const col of node.data.columns) {
      let modifiers = "";
      if (col.is_pk) modifiers += " PK";

      const safeId = sanitizeHandleId(col.column_name);
      // ⚡ Bolt: O(1) lookups instead of O(E) array search for every column
      const isFk =
        fkNodeColumnPairs.has(`${node.id}:${safeId}`) ||
        (fkNodesWithoutHandles.has(node.id) && node.data.badges?.fk);

      if (isFk && !col.is_pk) modifiers += " FK";

      // Mermaid data types should be alphanumeric without spaces
      const safeType = col.data_type.replace(/[^a-zA-Z0-9_]/g, "_");
      output += `    ${safeType} ${sanitizeString(col.column_name)}${modifiers}\n`;
    }
    output += "  }\n";
  }

  for (const edge of edges) {
    // ⚡ Bolt: O(1) lookups instead of O(N) array search for every edge
    const sourceNode = nodesById.get(edge.source);
    const targetNode = nodesById.get(edge.target);

    if (sourceNode && targetNode) {
      output += `  "${sanitizeString(targetNode.data.title)}" ||--o{ "${sanitizeString(sourceNode.data.title)}" : "${sanitizeString(String(edge.label || "rel"))}"\n`;
    }
  }

  return output;
}
