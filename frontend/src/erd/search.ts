import type { Node } from "@xyflow/react";

import type { TableNodeData } from "./convert";

const nodeSearchTextCache = new WeakMap<TableNodeData, string>();

function getNodeSearchText(node: Node<TableNodeData>): string {
  let text = nodeSearchTextCache.get(node.data);
  if (text !== undefined) return text;

  const parts: string[] = [];
  if (node.data.title) parts.push(node.data.title);
  if (node.data.comment) parts.push(node.data.comment);

  for (const col of node.data.columns) {
    if (col.column_name) parts.push(col.column_name);
    if (col.data_type) parts.push(col.data_type);
    if (col.column_comment) parts.push(col.column_comment);
  }

  text = parts.join(" ").toLocaleLowerCase();
  nodeSearchTextCache.set(node.data, text);
  return text;
}

export function tableNodeMatchesSearch(
  node: Node<TableNodeData>,
  search: string | string[],
): boolean {
  const terms = Array.isArray(search)
    ? search
    : Array.from(
        new Set(search.trim().toLocaleLowerCase().split(/\s+/).filter(Boolean)),
      );
  if (terms.length === 0) return false;

  const nodeText = getNodeSearchText(node);
  return terms.every((term) => nodeText.includes(term));
}

export function findSearchMatchedNodeIds(
  nodes: Array<Node<TableNodeData>>,
  search: string,
): Set<string> {
  const matches = new Set<string>();
  // ⚡ Bolt: Parse search terms ONCE outside the loop (O(1)) instead of inside tableNodeMatchesSearch for every node (O(N)),
  // eliminating redundant string allocations, regex splits, and Sets per node.
  const terms = Array.from(
    new Set(search.trim().toLocaleLowerCase().split(/\s+/).filter(Boolean)),
  );
  if (terms.length === 0) return matches;

  for (const node of nodes) {
    if (tableNodeMatchesSearch(node, terms)) {
      matches.add(node.id);
    }
  }
  return matches;
}
