import type { Node } from "@xyflow/react";

import type { TableNodeData } from "./convert";

type SearchSourceField = string | null | undefined;
type ColumnSearchSource = [SearchSourceField, SearchSourceField, SearchSourceField];

interface NodeSearchFieldsCacheEntry {
  title: SearchSourceField;
  comment: SearchSourceField;
  columns: ColumnSearchSource[];
  fields: string[];
}

const nodeSearchFieldsCache = new WeakMap<
  TableNodeData,
  NodeSearchFieldsCacheEntry
>();

function cacheMatchesData(
  cached: NodeSearchFieldsCacheEntry,
  data: TableNodeData,
): boolean {
  if (cached.title !== data.title || cached.comment !== data.comment) return false;
  if (cached.columns.length !== data.columns.length) return false;

  for (let index = 0; index < data.columns.length; index += 1) {
    const cachedColumn = cached.columns[index];
    const column = data.columns[index];
    if (
      cachedColumn[0] !== column.column_name ||
      cachedColumn[1] !== column.data_type ||
      cachedColumn[2] !== column.column_comment
    ) {
      return false;
    }
  }
  return true;
}

function getSearchFields(data: TableNodeData): string[] {
  const cached = nodeSearchFieldsCache.get(data);
  if (cached !== undefined && cacheMatchesData(cached, data)) return cached.fields;

  const fields: string[] = [];
  if (data.title) fields.push(data.title.toLocaleLowerCase());
  if (data.comment) fields.push(data.comment.toLocaleLowerCase());

  const columns: ColumnSearchSource[] = [];
  for (const column of data.columns) {
    const source: ColumnSearchSource = [
      column.column_name,
      column.data_type,
      column.column_comment,
    ];
    columns.push(source);
    for (const value of source) {
      if (value) fields.push(value.toLocaleLowerCase());
    }
  }

  nodeSearchFieldsCache.set(data, {
    title: data.title,
    comment: data.comment,
    columns,
    fields,
  });
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
