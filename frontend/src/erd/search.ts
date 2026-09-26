import type { Node } from "@xyflow/react";

import type { TableNodeData } from "./convert";

// ⚡ Bolt: Memoize expensive search string derivations using a WeakMap keyed by node.data.
// Node position updates create new object references on every frame (60fps), but data identity remains stable.
// This prevents redundant string concatenations and toLocaleLowerCase allocations during dragging.
const searchableTextCache = new WeakMap<TableNodeData, string>();

function getSearchableText(data: TableNodeData): string {
  let text = searchableTextCache.get(data);
  if (text !== undefined) return text;

  const parts: string[] = [];
  if (data.title) parts.push(data.title);
  if (data.comment) parts.push(data.comment);

  for (const column of data.columns) {
    if (column.column_name) parts.push(column.column_name);
    if (column.data_type) parts.push(column.data_type);
    if (column.column_comment) parts.push(column.column_comment);
  }

  // Use space as separator to prevent cross-field matches since terms are split by whitespace
  text = parts.join(" ").toLocaleLowerCase();
  searchableTextCache.set(data, text);
  return text;
}

function nodeIncludesTerm(node: Node<TableNodeData>, term: string): boolean {
  return getSearchableText(node.data).includes(term);
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
