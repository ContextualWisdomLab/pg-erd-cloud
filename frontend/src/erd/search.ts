import type { Node } from "@xyflow/react";

import type { TableNodeData } from "./convert";

function fieldIncludes(value: string | null | undefined, term: string): boolean {
  if (value === null || value === undefined) {
    return false;
  }
  const str = String(value);
  if (str === "") {
    return false;
  }
  return str.toLocaleLowerCase().includes(term);
}

function nodeIncludesTerm(node: Node<TableNodeData>, term: string): boolean {
  if (fieldIncludes(node.data.title, term)) return true;
  if (fieldIncludes(node.data.comment, term)) return true;

  for (let i = 0; i < node.data.columns.length; i++) {
    const column = node.data.columns[i];
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

  for (let i = 0; i < terms.length; i++) {
     if (!nodeIncludesTerm(node, terms[i])) {
         return false;
     }
  }
  return true;
}

export function findSearchMatchedNodeIds(
  nodes: Array<Node<TableNodeData>>,
  search: string,
): Set<string> {
  const matches = new Set<string>();
  const terms = getSearchTerms(search);
  if (terms.length === 0) return matches;

  for (let i = 0; i < nodes.length; i++) {
    const node = nodes[i];
    let allMatch = true;
    for (let j = 0; j < terms.length; j++) {
       if (!nodeIncludesTerm(node, terms[j])) {
           allMatch = false;
           break;
       }
    }
    if (allMatch) {
      matches.add(node.id);
    }
  }
  return matches;
}
