import { memo } from "react";
import { Handle, Position, type Node, type NodeProps } from "@xyflow/react";

import { sourceColumnHandleId, targetColumnHandleId } from "./handleUtils";

const MAX_RENDERED_COLUMNS = 25;

const HTML_TEXT_ESCAPE_RE = /[&<>"']/g;
const HTML_TEXT_REPLACEMENTS: Record<string, string> = {
  "&": "&amp;",
  "<": "&lt;",
  ">": "&gt;",
  '"': "&quot;",
  "'": "&#39;",
};

function escapeHtmlText(value: string): string {
  return value.replace(
    HTML_TEXT_ESCAPE_RE,
    (char) => HTML_TEXT_REPLACEMENTS[char] ?? char,
  );
}

type Column = {
  column_name: string;
  data_type: string;
  is_not_null: boolean;
  is_pk?: boolean;
  column_comment?: string | null;
  example_value?: string | number | boolean | null;
};

type TableNodeData = {
  title: string;
  comment?: string | null;
  columns: Column[];
  indexes?: Array<{
    index_name: string;
    columns: string[];
    access_method: string;
    strength?: string;
  }>;
  badges?: { pk?: boolean; fk?: boolean };
};

type TableNodeNode = Node<TableNodeData, "tableNode">;

function formatExample(value: Column["example_value"]): string | null {
  if (value === null || value === undefined) return null;
  const text = String(value).trim();
  return text ? text : null;
}

function TableNode(props: NodeProps<TableNodeNode>) {
  const { data } = props;
  return (
    <div className="tableNode">
      <Handle type="target" position={Position.Top} />
      <div className="tableNode__title">
        <span className="tableNode__titleText">
          <span>{data.title}</span>
          {data.comment ? (
            <span className="tableNode__titleComment">
              {escapeHtmlText(data.comment)}
            </span>
          ) : null}
        </span>
        <span style={{ display: "inline-flex", gap: 6 }}>
          {data.badges?.pk ? (
            <span className="tableNode__badge">PK</span>
          ) : null}
          {data.badges?.fk ? (
            <span className="tableNode__badge">FK</span>
          ) : null}
        </span>
      </div>
      <div className="tableNode__cols">
        {data.columns.slice(0, MAX_RENDERED_COLUMNS).map((c) => {
          const example = formatExample(c.example_value);
          return (
            <div key={c.column_name} className="tableNode__col">
              <Handle
                type="target"
                position={Position.Left}
                id={targetColumnHandleId(c.column_name)}
                className="colHandle"
              />
              <span className="tableNode__colIdentity">
                <span className="tableNode__colName">{c.column_name}</span>
                {c.column_comment ? (
                  <span className="tableNode__colComment">
                    {escapeHtmlText(c.column_comment)}
                  </span>
                ) : null}
                {example ? (
                  <span className="tableNode__colExample">
                    e.g. {escapeHtmlText(example)}
                  </span>
                ) : null}
              </span>
              <span className="tableNode__colType">{c.data_type}</span>
              {c.is_pk ? <span className="tableNode__badge">PK</span> : null}
              {c.is_not_null ? (
                <span className="tableNode__badge">NOT NULL</span>
              ) : null}
              <Handle
                type="source"
                position={Position.Right}
                id={sourceColumnHandleId(c.column_name)}
                className="colHandle"
              />
            </div>
          );
        })}
        {data.columns.length > MAX_RENDERED_COLUMNS ? (
          <div className="tableNode__more">
            … {data.columns.length - MAX_RENDERED_COLUMNS} more
          </div>
        ) : null}
        {data.indexes?.length ? (
          <div className="tableNode__indexes" aria-label="추천 인덱스">
            <div className="tableNode__indexHeading">Indexes</div>
            {data.indexes.slice(0, 4).map((index) => (
              <div key={index.index_name} className="tableNode__index">
                <span className="tableNode__indexName">
                  {index.index_name}
                </span>
                <span className="tableNode__indexCols">
                  ({index.columns.join(", ")})
                </span>
              </div>
            ))}
            {data.indexes.length > 4 ? (
              <div className="tableNode__more">
                … {data.indexes.length - 4} more indexes
              </div>
            ) : null}
          </div>
        ) : null}
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
    prev.data.badges?.pk === next.data.badges?.pk &&
    prev.data.badges?.fk === next.data.badges?.fk
  );
});
