import type { Node } from "@xyflow/react";

import type { TableNodeData } from "./convert";

const searchCache = new WeakMap<TableNodeData, string>();

function getNodeSearchText(data: TableNodeData): string {
  let text = searchCache.get(data);
  if (text !== undefined) return text;

  const parts: string[] = [];
  if (data.title) parts.push(data.title.toLocaleLowerCase());
  if (data.comment) parts.push(data.comment.toLocaleLowerCase());

  for (const column of data.columns) {
    if (column.column_name) parts.push(column.column_name.toLocaleLowerCase());
    if (column.data_type) parts.push(column.data_type.toLocaleLowerCase());
    if (column.column_comment) parts.push(column.column_comment.toLocaleLowerCase());
  }

  // ⚡ Bolt: Join with a control character to prevent cross-boundary false matches
  text = parts.join("\0");
  searchCache.set(data, text);
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
  const nodeText = getNodeSearchText(node.data);
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
