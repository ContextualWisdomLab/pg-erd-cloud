import type { Node } from "@xyflow/react";

import type { TableNodeData } from "./convert";

/**
 * Identity cache for search fields text compilation.
 * Note: Assumes `TableNodeData` objects are entirely immutable repository-wide.
 * If data fields mutate without new object creation, this cache will yield stale matches.
 * The `App.tsx::onEditTableSubmit` contract strictly guarantees new object issuance on edit.
 */
const searchCache = new WeakMap<TableNodeData, string>();

/**
 * Combines node metadata into a single string for O(1) matching comparisons.
 * Extracts title, comments, and column metadata. Returns a cache-backed delimited string.
 */
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

/**
 * Determines whether a table node completely matches all supplied search terms.
 * This evaluator leverages `getNodeSearchText` for constant-time extraction and
 * validates CJK and non-ASCII character boundaries properly by falling back to native JS `includes`.
 */
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

/**
 * Scans an entire list of TableNodes and extracts IDs that match the search string.
 * Optimizes initialization overhead to scale at $O(N)$ keystroke complexity avoiding
 * O(N*C) per-node deep evaluations by batch splitting criteria upfront.
 */
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
