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

export function findSearchMatchedNodeIds(
  nodes: Array<Node<TableNodeData>>,
  search: string,
  cache?: WeakMap<TableNodeData, boolean>,
): Set<string> {
  const matches = new Set<string>();
  // ⚡ Bolt: Parse search terms ONCE outside the loop (O(1)) instead of inside tableNodeMatchesSearch for every node (O(N)),
  // eliminating redundant string allocations, regex splits, and Sets per node.
  const terms = Array.from(
    new Set(search.trim().toLocaleLowerCase().split(/\s+/).filter(Boolean)),
  );
  if (terms.length === 0) return matches;

  for (const node of nodes) {
    let isMatch = false;
    if (cache) {
      let cachedMatch = cache.get(node.data);
      if (cachedMatch === undefined) {
        cachedMatch = tableNodeMatchesSearch(node, terms);
        cache.set(node.data, cachedMatch);
      }
      isMatch = cachedMatch;
    } else {
      isMatch = tableNodeMatchesSearch(node, terms);
    }

    if (isMatch) {
      matches.add(node.id);
    }
  }
  return matches;
}
