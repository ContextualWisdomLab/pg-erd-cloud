import type { Node } from "@xyflow/react";

import type { TableNodeData } from "./convert";

function fieldIncludes(value: string | null | undefined, term: string): boolean {
  return Boolean(value && value.toLocaleLowerCase().includes(term));
}

function nodeIncludesTerm(node: Node<TableNodeData>, term: string): boolean {
  if (fieldIncludes(node.data.title, term)) return true;
  if (fieldIncludes(node.data.comment, term)) return true;

  for (const column of node.data.columns) {
    if (fieldIncludes(column.column_name, term)) return true;
    if (fieldIncludes(column.data_type, term)) return true;
    if (fieldIncludes(column.column_comment, term)) return true;
  }

  return false;
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

// ⚡ Bolt: WeakMap to cache search matches by node.data.
// Since `node.data` remains stable during drags, this avoids re-evaluating the O(N*C) search function
// across all nodes at 60fps when dragging while a search filter is active.
const searchCache = new WeakMap<TableNodeData, Map<string, boolean>>();

export function findSearchMatchedNodeIds(
  nodes: Array<Node<TableNodeData>>,
  search: string,
): Set<string> {
  const matches = new Set<string>();
  // ⚡ Bolt: Parse search terms ONCE outside the loop (O(1)) instead of inside tableNodeMatchesSearch for every node (O(N)),
  // eliminating redundant string allocations, regex splits, and Sets per node.
  const trimmedSearch = search.trim().toLocaleLowerCase();
  const terms = Array.from(
    new Set(trimmedSearch.split(/\s+/).filter(Boolean)),
  );
  if (terms.length === 0) return matches;

  // Use a predictable cache key for this search.
  const searchKey = terms.join(" ");

  for (const node of nodes) {
    let nodeCache = searchCache.get(node.data);
    if (!nodeCache) {
      nodeCache = new Map();
      searchCache.set(node.data, nodeCache);
    }

    let isMatch = nodeCache.get(searchKey);
    if (isMatch === undefined) {
      isMatch = tableNodeMatchesSearch(node, terms);
      nodeCache.set(searchKey, isMatch);
    }

    if (isMatch) {
      matches.add(node.id);
    }
  }
  return matches;
}
