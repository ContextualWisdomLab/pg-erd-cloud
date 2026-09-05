import type { Node } from "@xyflow/react";

import type { TableNodeData } from "./convert";

// ⚡ Bolt: Cache lowercased search strings keyed by TableNodeData to prevent redundant
// string allocations and lowercasing during React Flow re-renders where `node` references change but `node.data` is stable.
const nodeSearchFieldsCache = new WeakMap<TableNodeData, string[]>();

function getSearchFields(data: TableNodeData): string[] {
  let fields = nodeSearchFieldsCache.get(data);
  if (fields !== undefined) return fields;

  fields = [];
  if (data.title) fields.push(data.title.toLocaleLowerCase());
  if (data.comment) fields.push(data.comment.toLocaleLowerCase());

  for (const column of data.columns) {
    if (column.column_name) fields.push(column.column_name.toLocaleLowerCase());
    if (column.data_type) fields.push(column.data_type.toLocaleLowerCase());
    if (column.column_comment) fields.push(column.column_comment.toLocaleLowerCase());
  }
  nodeSearchFieldsCache.set(data, fields);
  return fields;
}

function nodeIncludesTerm(node: Node<TableNodeData>, term: string): boolean {
  const fields = getSearchFields(node.data);
  for (const field of fields) {
    if (field.includes(term)) return true;
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
