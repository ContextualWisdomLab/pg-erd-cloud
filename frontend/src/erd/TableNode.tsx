import { memo, type CSSProperties } from "react";
import { Handle, Position, type Node, type NodeProps } from "@xyflow/react";

import { normalizeBusinessGroupColor } from "./businessGroups";
import { TableNodeColumn } from "./components/TableNodeColumn";
import { TableNodeTitle } from "./components/TableNodeTitle";
import { TableNodeIndexes } from "./components/TableNodeIndexes";
import type { Column, TableNodeData } from "./types";

const MAX_RENDERED_COLUMNS = 25;

type TableNodeNode = Node<TableNodeData, "tableNode">;

function TableNode(props: NodeProps<TableNodeNode>) {
  const { data } = props;
  const groupColor = data.businessGroup
    ? normalizeBusinessGroupColor(data.businessGroup.color)
    : undefined;
  const style = data.businessGroup
    ? ({
        "--table-group-color": groupColor,
      } as CSSProperties)
    : undefined;

  // User-supplied labels/comments are rendered as React text nodes; do not
  // switch these fields to raw HTML rendering.
  return (
    <div
      className={`tableNode${data.businessGroup ? " tableNode--grouped" : ""}`}
      style={style}
    >
      <Handle type="target" position={Position.Top} />
      <TableNodeTitle
        title={data.title}
        comment={data.comment}
        businessGroup={data.businessGroup}
        badges={data.badges}
      />
      <div className="tableNode__cols">
        {data.columns.slice(0, MAX_RENDERED_COLUMNS).map((c) => (
          <TableNodeColumn key={c.column_name} c={c} />
        ))}
        {data.columns.length > MAX_RENDERED_COLUMNS ? (
          <div className="tableNode__more">
            … {data.columns.length - MAX_RENDERED_COLUMNS} more
          </div>
        ) : null}
        <TableNodeIndexes indexes={data.indexes || []} />
      </div>
      <Handle type="source" position={Position.Bottom} />
    </div>
  );
}

function isSameRenderedColumns(
  prevCols: Column[],
  nextCols: Column[],
): boolean {
  if (prevCols.length !== nextCols.length) return false;

  // The component only renders the first MAX_RENDERED_COLUMNS and the "… N more" count.
  const limit = Math.min(
    MAX_RENDERED_COLUMNS,
    prevCols.length,
    nextCols.length,
  );
  for (let i = 0; i < limit; i += 1) {
    const a = prevCols[i];
    const b = nextCols[i];
    if (a.column_name !== b.column_name) return false;
    if (a.data_type !== b.data_type) return false;
    if (a.is_not_null !== b.is_not_null) return false;
    if (a.is_pk !== b.is_pk) return false;
    if (a.column_comment !== b.column_comment) return false;
    if (a.example_value !== b.example_value) return false;
  }
  return true;
}

export default memo(TableNode, (prev, next) => {
  // React Flow typically provides new node objects when data changes.
  // This comparator is a conservative safeguard for the most relevant fields.
  // Note: if upstream mutates `columns` in-place between renders, no memo comparator can
  // reliably detect it. Prefer immutable updates from the graph producer.
  return (
    prev.data.title === next.data.title &&
    prev.data.comment === next.data.comment &&
    isSameRenderedColumns(prev.data.columns, next.data.columns) &&
    prev.data.indexes === next.data.indexes &&
    prev.data.businessGroup?.id === next.data.businessGroup?.id &&
    prev.data.businessGroup?.name === next.data.businessGroup?.name &&
    prev.data.businessGroup?.color === next.data.businessGroup?.color &&
    prev.data.badges?.pk === next.data.badges?.pk &&
    prev.data.badges?.fk === next.data.badges?.fk
  );
});
