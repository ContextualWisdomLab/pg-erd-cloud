import type { Node } from "@xyflow/react";

import type { TableNodeData } from "./convert";

// ⚡ Bolt: Consolidate searchable text into a single string per node to avoid redundant
// .toLocaleLowerCase() calls and enable fast substring matching via indexOf.
function nodeSearchText(node: Node<TableNodeData>): string {
  let text = "";
  if (node.data.title) text += node.data.title + " ";
  if (node.data.comment) text += node.data.comment + " ";
  for (let i = 0; i < node.data.columns.length; i++) {
    const col = node.data.columns[i];
    if (col.column_name) text += col.column_name + " ";
    if (col.data_type) text += col.data_type + " ";
    if (col.column_comment) text += col.column_comment + " ";
  }
  return text.toLocaleLowerCase();
}

function getSearchTerms(search: string): string[] {
  return Array.from(
    new Set(search.trim().toLocaleLowerCase().split(/\s+/).filter(Boolean)),
  );
}

export function tableNodeMatchesSearch(
  node: Node<TableNodeData>,
  search: string,
): boolean {
  const terms = getSearchTerms(search);
  if (terms.length === 0) return false;

  const searchText = nodeSearchText(node);
  for (let i = 0; i < terms.length; i++) {
    if (searchText.indexOf(terms[i]) === -1) {
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

  // ⚡ Bolt: Parse search terms exactly once before iterating over nodes,
  // replacing O(N*M) redundant string parsing overhead with a single O(M) operation.
  const terms = getSearchTerms(search);
  if (terms.length === 0) return matches;

  for (let i = 0; i < nodes.length; i++) {
    const node = nodes[i];
    const searchText = nodeSearchText(node);
    let matched = true;
    for (let j = 0; j < terms.length; j++) {
      if (searchText.indexOf(terms[j]) === -1) {
        matched = false;
        break;
      }
    }
    if (matched) {
      matches.add(node.id);
    }
  }
  return matches;
}
