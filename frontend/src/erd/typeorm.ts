import type { Node } from "@xyflow/react";
import type { TableNodeData } from "./convert";

function mapToTypeORMType(pgType: string): string {
  const t = pgType.toLowerCase();
  if (t.includes("int") || t.includes("serial")) return "int";
  if (t.includes("char") || t.includes("text") || t.includes("uuid")) return "varchar";
  if (t.includes("bool")) return "boolean";
  if (t.includes("date")) return "date";
  if (t.includes("time")) return "timestamp";
  if (t.includes("float") || t.includes("double") || t.includes("real")) return "float";
  if (t.includes("numeric") || t.includes("decimal")) return "decimal";
  if (t.includes("json")) return "json";
  return "varchar";
}

function mapToTsType(pgType: string): string {
  const t = pgType.toLowerCase();
  if (t.includes("int") || t.includes("serial") || t.includes("float") || t.includes("double") || t.includes("numeric") || t.includes("real") || t.includes("decimal")) return "number";
  if (t.includes("bool")) return "boolean";
  if (t.includes("date") || t.includes("time")) return "Date";
  if (t.includes("json")) return "any";
  return "string";
}

function sanitizeIdentifier(name: string): string {
  let sanitized = name.replace(/[^a-zA-Z0-9_]/g, "");
  if (!/^[a-zA-Z_]/.test(sanitized)) {
    sanitized = "_" + sanitized;
  }
  return sanitized || "_unnamed";
}

export function exportTypeORM(nodes: Node<TableNodeData>[]): string {
  if (nodes.length === 0) return "// No tables to export\n";

  let output = `import { Entity, PrimaryGeneratedColumn, Column, PrimaryColumn } from "typeorm";\n\n`;

  for (const node of nodes) {
    const rawTableName = node.data.title.split('.').pop() || node.data.title;
    const tableName = sanitizeIdentifier(rawTableName);
    const modelName = tableName.replace(/(^\w|-\w|_\w)/g, (m) => m.replace(/-|_/, "").toUpperCase());

    output += `@Entity("${tableName}")\nexport class ${modelName} {\n`;
    for (const col of node.data.columns) {
      const fieldName = sanitizeIdentifier(col.column_name);
      const ormType = mapToTypeORMType(col.data_type);
      const tsType = mapToTsType(col.data_type);

      if (col.is_pk) {
        if (col.data_type.toLowerCase().includes("serial")) {
          output += `  @PrimaryGeneratedColumn()\n`;
        } else {
          output += `  @PrimaryColumn({ type: "${ormType}" })\n`;
        }
      } else {
        const nullable = !col.is_not_null;
        output += `  @Column({ type: "${ormType}"${nullable ? ", nullable: true" : ""} })\n`;
      }
      output += `  ${fieldName}${!col.is_not_null ? "?" : "!"}: ${tsType};\n\n`;
    }
    output += `}\n\n`;
  }

  return output.trim() + "\n";
}
