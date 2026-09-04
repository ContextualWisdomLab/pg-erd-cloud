import type { Node, Edge } from "@xyflow/react";
import type { TableNodeData } from "./convert";

function sanitizeClassName(name: string): string {
  let sanitized = name.replace(/[^a-zA-Z0-9_]/g, "_");
  if (!/^[a-zA-Z]/.test(sanitized)) {
    sanitized = "Entity_" + sanitized;
  }
  // Convert to PascalCase
  return sanitized.split('_').map(part => part.charAt(0).toUpperCase() + part.slice(1)).join('');
}

function sanitizeFieldName(name: string): string {
  let sanitized = name.replace(/[^a-zA-Z0-9_]/g, "_");
  if (!/^[a-zA-Z]/.test(sanitized)) {
    sanitized = "field_" + sanitized;
  }
  return sanitized;
}

function mapToTsType(pgType: string): string {
  const t = pgType.toLowerCase();
  if (t.includes("int") || t.includes("serial") || t.includes("float") || t.includes("double") || t.includes("numeric") || t.includes("real") || t.includes("decimal")) {
    return "number";
  }
  if (t.includes("char") || t.includes("text") || t.includes("uuid")) {
    return "string";
  }
  if (t.includes("bool")) {
    return "boolean";
  }
  if (t.includes("time") || t.includes("date")) {
    return "Date";
  }
  if (t.includes("json")) {
    return "any";
  }
  if (t.includes("bytea")) {
    return "Buffer";
  }
  return "string"; // fallback
}

export function exportTypeOrm(
  nodes: Node<TableNodeData>[],
  edges: Edge[],
): string {
  if (nodes.length === 0) {
    return "// No tables to export\n";
  }

  let output = `import { Entity, PrimaryColumn, PrimaryGeneratedColumn, Column, ManyToOne, OneToMany, JoinColumn } from 'typeorm';\n\n`;

  const nodesById = new Map<string, Node<TableNodeData>>();
  for (const n of nodes) {
    nodesById.set(n.id, n);
  }

  const incomingRelationsByNode = new Map<string, Array<{ relationName: string, sourceModel: string, sourceField: string }>>();
  const edgesProcessed = new Map<string, { sourceModel: string, targetModel: string, sourceFields: string[], targetFields: string[], relationName: string }>();

  for (const edge of edges) {
    const sourceNode = nodesById.get(edge.source);
    const targetNode = nodesById.get(edge.target);
    if (!sourceNode || !targetNode) continue;

    const relName = sanitizeFieldName(String(edge.label || `${sourceNode.data.title}_${targetNode.data.title}`));

    let sourceField = "";
    if (edge.sourceHandle?.startsWith("src-")) {
      sourceField = edge.sourceHandle.slice(4);
    }

    let targetField = "id"; // fallback
    if (edge.targetHandle?.startsWith("tgt-")) {
      targetField = edge.targetHandle.slice(4);
    }

    if (sourceField) {
      const relList = incomingRelationsByNode.get(edge.target) || [];
      relList.push({
        relationName: relName,
        sourceModel: sanitizeClassName(sourceNode.data.title),
        sourceField: sanitizeFieldName(sourceField),
      });
      incomingRelationsByNode.set(edge.target, relList);

      edgesProcessed.set(edge.id, {
        sourceModel: sanitizeClassName(sourceNode.data.title),
        targetModel: sanitizeClassName(targetNode.data.title),
        sourceFields: [sanitizeFieldName(sourceField)],
        targetFields: [sanitizeFieldName(targetField)],
        relationName: relName
      });
    }
  }

  for (const node of nodes) {
    const modelName = sanitizeClassName(node.data.title);
    output += `@Entity({ name: '${node.data.title}' })\n`;
    output += `export class ${modelName} {\n`;

    for (const col of node.data.columns) {
      const fieldName = sanitizeFieldName(col.column_name);
      const tsType = mapToTsType(col.data_type);

      const isOptional = !col.is_not_null;
      const tsNull = isOptional ? " | null" : "";
      const optionalFlag = isOptional && !col.is_pk ? "?" : "!";

      let colOptions: string[] = [];
      if (fieldName !== col.column_name) colOptions.push(`name: '${col.column_name}'`);
      if (isOptional && !col.is_pk) colOptions.push(`nullable: true`);

      const optionsStr = colOptions.length > 0 ? `{ ${colOptions.join(', ')} }` : '';

      if (col.is_pk) {
        if (col.data_type.toLowerCase().includes("serial")) {
          output += `  @PrimaryGeneratedColumn(${optionsStr})\n`;
        } else {
          output += `  @PrimaryColumn(${optionsStr})\n`;
        }
      } else {
        output += `  @Column(${optionsStr})\n`;
      }

      output += `  ${fieldName}${optionalFlag}: ${tsType}${tsNull};\n\n`;

      // ManyToOne relations
      for (const edgeInfo of edgesProcessed.values()) {
        if (edgeInfo.sourceModel === modelName && edgeInfo.sourceFields.includes(fieldName)) {
          const relField = sanitizeFieldName(edgeInfo.targetModel) + "_" + fieldName;
          output += `  @ManyToOne(() => ${edgeInfo.targetModel})\n`;
          output += `  @JoinColumn({ name: '${col.column_name}', referencedColumnName: '${edgeInfo.targetFields[0]}' })\n`;
          output += `  ${relField}?: ${edgeInfo.targetModel};\n\n`;
        }
      }
    }

    // OneToMany back-relations
    const incoming = incomingRelationsByNode.get(node.id) || [];
    for (const inc of incoming) {
      const relFieldBase = inc.sourceModel.charAt(0).toLowerCase() + inc.sourceModel.slice(1);
      const relField = relFieldBase.endsWith("s") ? relFieldBase : relFieldBase + "s";
      output += `  @OneToMany(() => ${inc.sourceModel}, (child) => child.${modelName}_${inc.sourceField})\n`;
      output += `  ${relField}?: ${inc.sourceModel}[];\n\n`;
    }

    output += `}\n\n`;
  }

  return output.trim() + "\n";
}
