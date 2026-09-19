import type { Node } from "@xyflow/react";

import type { TableNodeData } from "./convert";

// ⚡ Bolt: Memoize expensive string concatenation and lowercasing for search using a WeakMap keyed by node.data.
// In React Flow, dragging nodes creates new Node references on every frame while node.data remains stable.
// This O(1) cache lookup prevents severe 60fps performance drops from redundant O(C) string operations per node during render cycles.
const searchHaystackCache = new WeakMap<TableNodeData, string>();

function getSearchHaystack(data: TableNodeData): string {
  let cached = searchHaystackCache.get(data);
  if (cached !== undefined) return cached;

  const parts: string[] = [];
  if (data.title) parts.push(data.title.toLocaleLowerCase());
  if (data.comment) parts.push(data.comment.toLocaleLowerCase());

  for (const column of data.columns) {
    if (column.column_name) parts.push(column.column_name.toLocaleLowerCase());
    if (column.data_type) parts.push(column.data_type.toLocaleLowerCase());
    if (column.column_comment) parts.push(column.column_comment.toLocaleLowerCase());
  }

  cached = parts.join('\x00');
  searchHaystackCache.set(data, cached);
  return cached;
}

function nodeIncludesTerm(node: Node<TableNodeData>, term: string): boolean {
  return getSearchHaystack(node.data).includes(term);
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
  return terms.every((term) => nodeIncludesTerm(node, term));
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
