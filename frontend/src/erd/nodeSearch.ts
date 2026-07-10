import type { Node } from "@xyflow/react";

import type { TableNodeData } from "./convert";

export function tableNodeMatchesSearch(
  node: Node<TableNodeData>,
  normalizedSearch: string,
): boolean {
  if (!normalizedSearch) return false;
  const { data } = node;

  if (data.title.toLocaleLowerCase().includes(normalizedSearch)) return true;
  if (
    data.comment &&
    data.comment.toLocaleLowerCase().includes(normalizedSearch)
  ) {
    return true;
  }

  for (const column of data.columns) {
    if (column.column_name.toLocaleLowerCase().includes(normalizedSearch)) {
      return true;
    }
    if (column.data_type.toLocaleLowerCase().includes(normalizedSearch)) {
      return true;
    }
    if (
      column.column_comment &&
      column.column_comment.toLocaleLowerCase().includes(normalizedSearch)
    ) {
      return true;
    }
  }

  return false;
}
