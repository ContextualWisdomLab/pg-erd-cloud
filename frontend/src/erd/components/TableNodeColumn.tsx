import { Handle, Position } from "@xyflow/react";
import { sourceColumnHandleId, targetColumnHandleId } from "../handleUtils";
import type { Column } from "../types";

function formatExample(value: Column["example_value"]): string | null {
  if (value === null || value === undefined) return null;
  const text = String(value).trim();
  return text ? text : null;
}

export function TableNodeColumn({ c }: { c: Column }) {
  const example = formatExample(c.example_value);
  return (
    <div className="tableNode__col">
      <Handle
        type="target"
        position={Position.Left}
        id={targetColumnHandleId(c.column_name)}
        className="colHandle"
      />
      <span className="tableNode__colIdentity">
        <span className="tableNode__colName">{c.column_name}</span>
        {c.column_comment ? (
          <span className="tableNode__colComment">{c.column_comment}</span>
        ) : null}
        {example ? (
          <span className="tableNode__colExample">e.g. {example}</span>
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
}
