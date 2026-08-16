import type { Node } from "@xyflow/react";

import type { TableNodeData } from "./convert";

const searchableTextCache = new WeakMap<TableNodeData, string>();

function getSearchableText(data: TableNodeData): string {
  const cachedText = searchableTextCache.get(data);
  if (cachedText !== undefined) return cachedText;

  const fields = [data.title, data.comment || ""];
  for (const column of data.columns) {
    fields.push(
      column.column_name,
      column.data_type,
      column.column_comment || "",
    );
  }

  const searchableText = fields.join(" ").toLocaleLowerCase();
  searchableTextCache.set(data, searchableText);
  return searchableText;
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
  for (const term of terms) {
    if (!text.includes(term)) return false;
  }
  return true;
}

export function findSearchMatchedNodeIds(
  nodes: Array<Node<TableNodeData>>,
  search: string,
): Set<string> {
  const matches = new Set<string>();
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
