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

export function getSearchTerms(search: string): string[] {
  // ⚡ Bolt: Avoid Array.from(new Set(search.split().filter())) which does multiple intermediate allocations
  const rawTerms = search.trim().toLocaleLowerCase().split(/\s+/);
  const terms: string[] = [];
  const seen = new Set<string>();

  for (let i = 0; i < rawTerms.length; i++) {
    const term = rawTerms[i];
    if (term && !seen.has(term)) {
      seen.add(term);
      terms.push(term);
    }
  }
  return terms;
}

export function tableNodeMatchesSearch(
  node: Node<TableNodeData>,
  search: string,
): boolean {
  const terms = getSearchTerms(search);
  if (terms.length === 0) return false;
  return terms.every((term) => nodeIncludesTerm(node, term));
}

export function findSearchMatchedNodeIds(
  nodes: Array<Node<TableNodeData>>,
  search: string,
): Set<string> {
  const matches = new Set<string>();
  const terms = getSearchTerms(search);
  if (terms.length === 0) return matches;

  for (const node of nodes) {
    if (terms.every((term) => nodeIncludesTerm(node, term))) {
      matches.add(node.id);
    }
  }
  return matches;
}
