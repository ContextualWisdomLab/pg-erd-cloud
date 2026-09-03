import type { Node, Edge } from "@xyflow/react";
import type { TableNodeData } from "./convert";
import { sanitizeHandleId } from "./handleUtils";

function sanitizeClassName(name: string): string {
  let sanitized = name.replace(/[^a-zA-Z0-9_]/g, "_");
  if (!/^[a-zA-Z]/.test(sanitized)) {
    sanitized = "Entity_" + sanitized;
  }
  return sanitized.split('_').map(part => part.charAt(0).toUpperCase() + part.slice(1)).join('');
}

function sanitizeFieldName(name: string): string {
  let sanitized = name.replace(/[^a-zA-Z0-9_]/g, "_");
  if (!/^[a-zA-Z]/.test(sanitized)) {
    sanitized = "field_" + sanitized;
  }
  return sanitized;
}

function mapToPyType(pgType: string): string {
  const t = pgType.toLowerCase();
  if (t.includes("int") || t.includes("serial")) return "int";
  if (t.includes("float") || t.includes("double") || t.includes("numeric") || t.includes("real") || t.includes("decimal")) return "Decimal";
  if (t.includes("char") || t.includes("text")) return "str";
  if (t.includes("uuid")) return "uuid.UUID";
  if (t.includes("bool")) return "bool";
  if (t.includes("time") || t.includes("date")) return "dt.datetime";
  if (t.includes("json")) return "dict | list";
  if (t.includes("bytea")) return "bytes";
  return "str";
}

export function exportSqlAlchemy(
  nodes: Node<TableNodeData>[],
  edges: Edge[],
): string {
  if (nodes.length === 0) {
    return "# No tables to export\n";
  }

  let output = `from __future__ import annotations

import datetime as dt
import uuid
from decimal import Decimal

from sqlalchemy import ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    pass

`;

  const nodesById = new Map<string, Node<TableNodeData>>();
  for (const n of nodes) {
    nodesById.set(n.id, n);
  }

  const fkNodeColumnPairs = new Set<string>();
  const fkNodesWithoutHandles = new Set<string>();
  const edgesProcessed = new Map<string, { sourceModel: string, targetModel: string, sourceFields: string[], targetFields: string[], targetTableName: string }>();

  for (const edge of edges) {
    const sourceNode = nodesById.get(edge.source);
    const targetNode = nodesById.get(edge.target);
    if (!sourceNode || !targetNode) continue;

    let sourceField = "";
    if (edge.sourceHandle?.startsWith("src-")) {
      sourceField = edge.sourceHandle.slice(4);
      fkNodeColumnPairs.add(`${edge.source}:${sourceField}`);
    } else if (!edge.sourceHandle) {
      fkNodesWithoutHandles.add(edge.source);
    }

    let targetField = "id"; // fallback
    if (edge.targetHandle?.startsWith("tgt-")) {
      targetField = edge.targetHandle.slice(4);
    }

    if (sourceField) {
      edgesProcessed.set(edge.id, {
        sourceModel: sanitizeClassName(sourceNode.data.title),
        targetModel: sanitizeClassName(targetNode.data.title),
        sourceFields: [sourceField],
        targetFields: [targetField],
        targetTableName: targetNode.data.title
      });
    }
  }

  for (const node of nodes) {
    const modelName = sanitizeClassName(node.data.title);
    output += `class ${modelName}(Base):\n`;
    if (node.data.comment) {
        output += `    """${node.data.comment.replace(/"""/g, "'''")}"""\n`;
    }
    output += `    __tablename__ = '${node.data.title}'\n\n`;

    if (node.data.columns.length === 0) {
      output += `    pass\n\n`;
      continue;
    }

    for (const col of node.data.columns) {
      const fieldName = sanitizeFieldName(col.column_name);
      let pyType = mapToPyType(col.data_type);

      const isOptional = !col.is_not_null;
      if (isOptional) pyType += " | None";

      let args: string[] = [];
      if (fieldName !== col.column_name) args.push(`'${col.column_name}'`);

      for (const [_, edgeInfo] of edgesProcessed) {
        if (edgeInfo.sourceModel === modelName && edgeInfo.sourceFields.includes(col.column_name)) {
          args.push(`ForeignKey('${edgeInfo.targetTableName}.${edgeInfo.targetFields[0]}')`);
        }
      }

      if (col.is_pk) args.push("primary_key=True");

      const mappedColumnCall = args.length > 0 ? `mapped_column(${args.join(", ")})` : `mapped_column()`;

      output += `    ${fieldName}: Mapped[${pyType}] = ${mappedColumnCall}\n`;
    }

    output += `\n`;
  }

  return output.trim() + "\n";
}
