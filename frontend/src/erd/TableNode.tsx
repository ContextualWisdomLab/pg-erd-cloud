import { memo, type CSSProperties, type ReactNode } from "react";
import { Handle, Position, type Node, type NodeProps } from "@xyflow/react";

import { normalizeBusinessGroupColor } from "./businessGroups";
import { sourceColumnHandleId, targetColumnHandleId } from "./handleUtils";

const MAX_RENDERED_COLUMNS = 25;

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
  businessGroup?: { id: string; name: string; color: string } | null;
  indexes?: Array<{
    index_name: string;
    columns: string[];
    access_method: string;
    strength?: string;
  }>;
  isDimmed?: boolean;
  isHighlighted?: boolean;
  badges?: { pk?: boolean; fk?: boolean };
};

type TableNodeNode = Node<TableNodeData, "tableNode">;

function AccessibleTruncatedText({
  className,
  text,
  children,
}: {
  className: string;
  text: string;
  children?: ReactNode;
}) {
  const accessibleText = text.trim();
  if (!accessibleText) {
    return <span className={className}>{children ?? text}</span>;
  }

  return (
    <span
      className={className}
      title={text}
      aria-label={text}
      tabIndex={0}
    >
      {children ?? text}
    </span>
  );
}

function formatExample(value: Column["example_value"]): string | null {
  if (value === null || value === undefined) return null;
  const text = String(value).trim();
  return text ? text : null;
}

function TableNode(props: NodeProps<TableNodeNode>) {
  const { data } = props;
  const accessibleTableName = data.title.trim() || "이름 없는";
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
  const className = [
    "tableNode",
    data.businessGroup ? "tableNode--grouped" : "",
    data.isDimmed ? "tableNode--dimmed" : "",
    data.isHighlighted ? "tableNode--highlighted" : "",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <div
      className={className}
      style={style}
      role="region"
      aria-label={`${accessibleTableName} 테이블`}
    >
      <Handle type="target" position={Position.Top} />
      <div className="tableNode__title">
        <span className="tableNode__titleText">
          <span>{data.title}</span>
          {data.comment ? (
            <AccessibleTruncatedText
              className="tableNode__titleComment"
              text={data.comment}
            />
          ) : null}
        </span>
        <span style={{ display: "inline-flex", gap: 6 }}>
          {data.businessGroup ? (
            <AccessibleTruncatedText
              className="tableNode__groupBadge"
              text={data.businessGroup.name}
            />
          ) : null}
          {data.badges?.pk ? (
            <abbr className="tableNode__badge" title="Primary Key">PK</abbr>
          ) : null}
          {data.badges?.fk ? (
            <abbr className="tableNode__badge" title="Foreign Key">FK</abbr>
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
                  <AccessibleTruncatedText
                    className="tableNode__colComment"
                    text={c.column_comment}
                  />
                ) : null}
                {example ? (
                  <AccessibleTruncatedText
                    className="tableNode__colExample"
                    text={`e.g. ${example}`}
                  >
                    e.g. {example}
                  </AccessibleTruncatedText>
                ) : null}
              </span>
              <span className="tableNode__colType">{c.data_type}</span>
              {c.is_pk ? (
                <abbr className="tableNode__badge" title="Primary Key">
                  PK
                </abbr>
              ) : null}
              {c.is_not_null ? (
                <span className="tableNode__badge" title="Not Null">
                  NOT NULL
                </span>
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
          <div
            className="tableNode__more"
            title={`생략된 컬럼이 ${data.columns.length - MAX_RENDERED_COLUMNS}개 더 있습니다`}
            aria-label={`생략된 컬럼이 ${data.columns.length - MAX_RENDERED_COLUMNS}개 더 있습니다`}
            tabIndex={0}
          >
            … {data.columns.length - MAX_RENDERED_COLUMNS} more
          </div>
        ) : null}
        {data.indexes?.length ? (
          <div className="tableNode__indexes" role="group" aria-label="추천 인덱스">
            <div className="tableNode__indexHeading">Indexes</div>
            {data.indexes.slice(0, 4).map((index) => {
              const columnsText = `(${index.columns.join(", ")})`;
              return (
                <div key={index.index_name} className="tableNode__index">
                  <AccessibleTruncatedText
                    className="tableNode__indexName"
                    text={index.index_name}
                  />
                  <AccessibleTruncatedText
                    className="tableNode__indexCols"
                    text={columnsText}
                  />
                </div>
              );
            })}
            {data.indexes.length > 4 ? (
              <div
                className="tableNode__more"
                title={`생략된 인덱스가 ${data.indexes.length - 4}개 더 있습니다`}
                aria-label={`생략된 인덱스가 ${data.indexes.length - 4}개 더 있습니다`}
                tabIndex={0}
              >
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
  if (prevCols === nextCols) return true;
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
  if (prev.data === next.data) return true;

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
    prev.data.isDimmed === next.data.isDimmed &&
    prev.data.isHighlighted === next.data.isHighlighted &&
    prev.data.badges?.pk === next.data.badges?.pk &&
    prev.data.badges?.fk === next.data.badges?.fk
  );
});
