import type { Node } from "@xyflow/react";
import type { TableNodeData } from "./convert";

function mapToSqlAlchemyType(pgType: string): string {
  const t = pgType.toLowerCase();
  if (t.includes("int") || t.includes("serial")) return "Integer";
  if (t.includes("char") || t.includes("text") || t.includes("uuid")) return "String";
  if (t.includes("bool")) return "Boolean";
  if (t.includes("date")) return "Date";
  if (t.includes("time")) return "DateTime";
  if (t.includes("float") || t.includes("double") || t.includes("real")) return "Float";
  if (t.includes("numeric") || t.includes("decimal")) return "Numeric";
  if (t.includes("json")) return "JSON";
  return "String";
}

export function exportSqlAlchemy(nodes: Node<TableNodeData>[]): string {
  if (nodes.length === 0) return "# No tables to export\n";

  let output = `from sqlalchemy import Column, Integer, String, Boolean, Date, DateTime, Float, Numeric, JSON\nfrom sqlalchemy.orm import declarative_base\n\nBase = declarative_base()\n\n`;

  for (const node of nodes) {
    const tableName = node.data.title.split('.').pop() || node.data.title;
    const modelName = tableName.replace(/(^\w|-\w|_\w)/g, (m) => m.replace(/-|_/, "").toUpperCase());

    output += `class ${modelName}(Base):\n`;
    output += `    __tablename__ = '${tableName}'\n\n`;

    for (const col of node.data.columns) {
      const fieldName = col.column_name;
      const saType = mapToSqlAlchemyType(col.data_type);
      const args = [];
      if (col.is_pk) args.push("primary_key=True");
      if (!col.is_not_null && !col.is_pk) args.push("nullable=True");
      else if (col.is_not_null && !col.is_pk) args.push("nullable=False");

      output += `    ${fieldName} = Column(${saType}${args.length > 0 ? ", " + args.join(", ") : ""})\n`;
    }
    output += `\n`;
  }

  return output.trim() + "\n";
}
