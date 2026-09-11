import type { Node, Edge } from "@xyflow/react";
import type { TableNodeData } from "./convert";
import { sanitizeHandleId } from "./handleUtils";

function sanitizeClassName(name: string): string {
  let sanitized = name.replace(/[^a-zA-Z0-9_]/g, "_");
  if (!/^[a-zA-Z]/.test(sanitized)) {
    sanitized = "Entity_" + sanitized;
  }
  return sanitized.charAt(0).toUpperCase() + sanitized.slice(1);
}

function sanitizePropertyName(name: string): string {
  let sanitized = name.replace(/[^a-zA-Z0-9_]/g, "_");
  if (!/^[a-zA-Z]/.test(sanitized)) {
    sanitized = "prop_" + sanitized;
  }
  return sanitized;
}

function mapToTsType(pgType: string): string {
  const t = pgType.toLowerCase();
  if (t.includes("int") || t.includes("serial") || t.includes("float") || t.includes("double") || t.includes("numeric") || t.includes("real") || t.includes("decimal")) {
    return "number";
  }
  if (t.includes("bool")) {
    return "boolean";
  }
  if (t.includes("time") || t.includes("date") || t.includes("timestamp")) {
    return "Date";
  }
  return "string";
}

export function exportTypeOrm(nodes: Node<TableNodeData>[], edges: Edge[]): string {
  if (nodes.length === 0) {
    return "// No tables to export\n";
  }

  let output = `import { Entity, PrimaryGeneratedColumn, Column, PrimaryColumn, ManyToOne, OneToMany, JoinColumn } from "typeorm";\n\n`;

  const nodesById = new Map<string, Node<TableNodeData>>();
  for (const n of nodes) {
    nodesById.set(n.id, n);
  }

  const fkNodeColumnPairs = new Set<string>();
  const fkNodesWithoutHandles = new Set<string>();
  const incomingRelationsByNode = new Map<string, Array<{ sourceModel: string, sourceField: string, targetField: string }>>();
  const edgesProcessed = new Map<string, { sourceModel: string, targetModel: string, sourceFields: string[], targetFields: string[] }>();

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

    let targetField = "id";
    if (edge.targetHandle?.startsWith("tgt-")) {
      targetField = edge.targetHandle.slice(4);
    }

    if (sourceField) {
      const relList = incomingRelationsByNode.get(edge.target) || [];
      relList.push({
        sourceModel: sanitizeClassName(sourceNode.data.title),
        sourceField: sanitizePropertyName(sourceField),
        targetField: sanitizePropertyName(targetField)
      });
      incomingRelationsByNode.set(edge.target, relList);

      edgesProcessed.set(edge.id, {
        sourceModel: sanitizeClassName(sourceNode.data.title),
        targetModel: sanitizeClassName(targetNode.data.title),
        sourceFields: [sanitizePropertyName(sourceField)],
        targetFields: [sanitizePropertyName(targetField)]
      });
    }
  }

  for (const node of nodes) {
    const className = sanitizeClassName(node.data.title);
    const tableNameParts = node.data.title.split('.');
    let tableName = node.data.title;
    let schemaName = 'public';

    if (tableNameParts.length > 1) {
      schemaName = tableNameParts[0];
      tableName = tableNameParts.slice(1).join('.');
    }

    output += `@Entity({ name: "${tableName}", schema: "${schemaName}" })\nexport class ${className} {\n`;

    for (const col of node.data.columns) {
      const propName = sanitizePropertyName(col.column_name);
      const tsType = mapToTsType(col.data_type);
      const isFk = fkNodeColumnPairs.has(`${node.id}:${sanitizeHandleId(col.column_name)}`) || (fkNodesWithoutHandles.has(node.id) && node.data.badges?.fk);

      let colDecorator = "@Column()";
      if (col.is_pk) {
        if (tsType === "number" && col.data_type.toLowerCase().includes("serial")) {
          colDecorator = "@PrimaryGeneratedColumn()";
        } else if (tsType === "string" && col.data_type.toLowerCase().includes("uuid")) {
          colDecorator = `@PrimaryGeneratedColumn("uuid")`;
        } else {
          colDecorator = "@PrimaryColumn()";
        }
      } else {
        const colOpts = [];
        colOpts.push(`name: "${col.column_name}"`);
        if (!col.is_not_null) colOpts.push(`nullable: true`);
        if (col.data_type) colOpts.push(`type: "${col.data_type}"`);
        colDecorator = `@Column({ ${colOpts.join(", ")} })`;
      }

      const optional = col.is_not_null ? "" : "?";
      output += `  ${colDecorator}\n  ${propName}${optional}: ${tsType};\n\n`;

      for (const [_, edgeInfo] of edgesProcessed) {
        if (edgeInfo.sourceModel === className && edgeInfo.sourceFields.includes(propName)) {
          const relProp = edgeInfo.targetModel.charAt(0).toLowerCase() + edgeInfo.targetModel.slice(1) + "_" + propName;
          output += `  @ManyToOne(() => ${edgeInfo.targetModel})\n  @JoinColumn({ name: "${col.column_name}", referencedColumnName: "${edgeInfo.targetFields[0]}" })\n  ${relProp}${optional}: ${edgeInfo.targetModel};\n\n`;
        }
      }
    }

    const incoming = incomingRelationsByNode.get(node.id) || [];
    for (const inc of incoming) {
      const relPropName = inc.sourceModel.charAt(0).toLowerCase() + inc.sourceModel.slice(1) + "s_" + inc.sourceField;
      output += `  @OneToMany(() => ${inc.sourceModel}, (e) => e.${inc.sourceModel.charAt(0).toLowerCase() + inc.sourceModel.slice(1)}_${inc.sourceField})\n  ${relPropName}: ${inc.sourceModel}[];\n\n`;
    }

    output += `}\n\n`;
  }

  return output.trim() + "\n";
}
