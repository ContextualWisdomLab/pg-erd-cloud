import type { Node } from "@xyflow/react";

import type { TableNodeData } from "./convert";

// ⚡ Bolt: Cache lowercased searchable text per node.data to avoid redundant string allocations
// and `.toLocaleLowerCase()` calls during 60fps React Flow node drag updates.
const searchableTextCache = new WeakMap<TableNodeData, string>();

function getSearchableText(data: TableNodeData): string {
  let text = searchableTextCache.get(data);
  if (text !== undefined) return text;

  const parts: string[] = [];
  if (data.title) parts.push(data.title.toLocaleLowerCase());
  if (data.comment) parts.push(data.comment.toLocaleLowerCase());

  for (const column of data.columns) {
    if (column.column_name) parts.push(column.column_name.toLocaleLowerCase());
    if (column.data_type) parts.push(column.data_type.toLocaleLowerCase());
    if (column.column_comment) parts.push(column.column_comment.toLocaleLowerCase());
  }

  // Join with space to prevent substring matches across field boundaries
  text = parts.join(" ");
  searchableTextCache.set(data, text);
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

  const text = getSearchableText(node.data);
  return terms.every((term) => text.includes(term));
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
