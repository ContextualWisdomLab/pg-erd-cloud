import type { Node } from "@xyflow/react";

import type { TableNodeData } from "./convert";

const searchableTextCache = new WeakMap<TableNodeData, string>();

/** @internal Test boundary seam: exposing cache miss count for deterministic test assertions. */
export const _searchCacheMetrics = { misses: 0 };

function getSearchableText(data: TableNodeData): string {
  let text = searchableTextCache.get(data);
  if (text !== undefined) return text;

  _searchCacheMetrics.misses++;

  text = (data.title || "") + " " + (data.comment || "");
  for (let i = 0; i < data.columns.length; i++) {
    const col = data.columns[i];
    text += " " + col.column_name + " " + col.data_type + " " + (col.column_comment || "");
  }

  text = text.toLocaleLowerCase();
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
  for (let i = 0; i < terms.length; i++) {
    if (!text.includes(terms[i])) return false;
  }
  return true;
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

  for (let i = 0; i < nodes.length; i++) {
    const node = nodes[i];
    if (tableNodeMatchesSearch(node, terms)) {
      matches.add(node.id);
    }
  }
  return matches;
}
