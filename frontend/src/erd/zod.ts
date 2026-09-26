import type { Node } from "@xyflow/react";
import type { TableNodeData } from "./convert";

function mapToZodType(pgType: string): string {
  const t = pgType.toLowerCase();
  if (t.includes("int") || t.includes("serial") || t.includes("float") || t.includes("double") || t.includes("numeric") || t.includes("real") || t.includes("decimal")) {
    return "z.number()";
  }
  if (t.includes("bool")) {
    return "z.boolean()";
  }
  if (t.includes("json")) {
    return "z.any()";
  }
  if (t.includes("date") || t.includes("time")) {
    return "z.string().datetime()";
  }
  return "z.string()";
}

export function exportZod(nodes: Node<TableNodeData>[]): string {
  if (nodes.length === 0) return "// No tables to export\n";

  let output = `import { z } from "zod";\n\n`;

  for (const node of nodes) {
    const tableName = node.data.title.split('.').pop() || node.data.title;
    const modelName = tableName.replace(/(^\w|-\w|_\w)/g, (m) => m.replace(/-|_/, "").toUpperCase());

    output += `export const ${modelName}Schema = z.object({\n`;
    for (const col of node.data.columns) {
      const fieldName = col.column_name;
      let zodType = mapToZodType(col.data_type);
      if (!col.is_not_null) {
        zodType += ".nullable()";
      }
      output += `  ${fieldName}: ${zodType},\n`;
    }
    output += `});\n\n`;
    output += `export type ${modelName} = z.infer<typeof ${modelName}Schema>;\n\n`;
  }
  return output.trim() + "\n";
}
