import type { Node, Edge } from "@xyflow/react";
import type { TableNodeData, ForeignKeyEdgeData } from "./convert";
import { sanitizeHandleId, decodeHandleId } from "./handleUtils";

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

  // Track all relationships coming INTO a target model
  const incomingRelationsByNode = new Map<string, Array<{ sourceModel: string, sourceField: string, targetField: string }>>();

  // Track relationship configurations for the source models
  const edgesProcessed = new Map<string, { sourceModel: string, targetModel: string, sourceFields: string[], targetFields: string[] }>();

  // Ensure unique class names
  const usedClassNames = new Map<string, string>();
  for (const node of nodes) {
    let baseName = sanitizeClassName(node.data.title.split('.').pop() || "table");
    let className = baseName;
    let counter = 1;
    while (Array.from(usedClassNames.values()).includes(className)) {
      className = `${baseName}_${counter}`;
      counter++;
    }
    usedClassNames.set(node.id, className);
  }

  for (const edge of edges) {
    const sourceNode = nodesById.get(edge.source);
    const targetNode = nodesById.get(edge.target);
    if (!sourceNode || !targetNode) continue;

    const sourceModel = usedClassNames.get(sourceNode.id)!;
    const targetModel = usedClassNames.get(targetNode.id)!;

    let sourceCols: string[] = [];
    let targetCols: string[] = [];

    const edgeData = edge.data as ForeignKeyEdgeData | undefined;

    if (edgeData?.sourceColumns && edgeData?.targetColumns) {
      sourceCols = [...edgeData.sourceColumns];
      targetCols = [...edgeData.targetColumns];

      for (const col of sourceCols) {
        fkNodeColumnPairs.add(`${edge.source}:${sanitizeHandleId(col)}`);
      }
    } else {
      let sourceField = "";
      if (edge.sourceHandle?.startsWith("src-")) {
        sourceField = decodeHandleId(edge.sourceHandle);
        fkNodeColumnPairs.add(`${edge.source}:${sanitizeHandleId(sourceField)}`);
      } else if (!edge.sourceHandle) {
        fkNodesWithoutHandles.add(edge.source);
      }

      let targetField = "id";
      if (edge.targetHandle?.startsWith("tgt-")) {
        targetField = decodeHandleId(edge.targetHandle);
      }

      if (sourceField) {
         sourceCols = [sourceField];
         targetCols = [targetField];
      }
    }

    if (sourceCols.length > 0) {
      const relList = incomingRelationsByNode.get(edge.target) || [];
      // Combine multiple columns into a signature for naming if necessary
      const combinedSourceField = sourceCols.map(sanitizePropertyName).join("_");
      const combinedTargetField = targetCols.map(sanitizePropertyName).join("_");

      relList.push({
        sourceModel,
        sourceField: combinedSourceField,
        targetField: combinedTargetField
      });
      incomingRelationsByNode.set(edge.target, relList);

      edgesProcessed.set(edge.id, {
        sourceModel,
        targetModel,
        sourceFields: sourceCols,
        targetFields: targetCols
      });
    }
  }

  for (const node of nodes) {
    const className = usedClassNames.get(node.id)!;
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

      let colDecorator = "";
      if (col.is_pk) {
        if (col.data_type.toLowerCase().includes("serial")) {
          colDecorator = `@PrimaryGeneratedColumn({ name: "${col.column_name}" })`;
        } else {
          const colOpts = [];
          colOpts.push(`name: "${col.column_name}"`);
          if (col.data_type) colOpts.push(`type: "${col.data_type}"`);
          colDecorator = `@PrimaryColumn({ ${colOpts.join(", ")} })`;
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
    }

    // Add forward relations
    for (const [_, edgeInfo] of edgesProcessed) {
      if (edgeInfo.sourceModel === className) {
        const relProp = edgeInfo.targetModel.charAt(0).toLowerCase() + edgeInfo.targetModel.slice(1) + "_" + edgeInfo.sourceFields.map(sanitizePropertyName).join("_");
        const isOptional = true; // Could map strictly based on is_not_null of source fields
        output += `  @ManyToOne(() => ${edgeInfo.targetModel})\n`;
        if (edgeInfo.sourceFields.length === 1) {
            output += `  @JoinColumn({ name: "${edgeInfo.sourceFields[0]}", referencedColumnName: "${edgeInfo.targetFields[0]}" })\n`;
        } else {
            const joinColumns = edgeInfo.sourceFields.map((sf, i) => `{ name: "${sf}", referencedColumnName: "${edgeInfo.targetFields[i]}" }`).join(", ");
            output += `  @JoinColumn([${joinColumns}])\n`;
        }
        output += `  ${relProp}?: ${edgeInfo.targetModel};\n\n`;
      }
    }

    // Add back relations
    const incoming = incomingRelationsByNode.get(node.id) || [];
    for (const inc of incoming) {
      const relPropName = inc.sourceModel.charAt(0).toLowerCase() + inc.sourceModel.slice(1) + "s_" + inc.sourceField;
      output += `  @OneToMany(() => ${inc.sourceModel}, (e) => e.${inc.sourceModel.charAt(0).toLowerCase() + inc.sourceModel.slice(1)}_${inc.sourceField})\n  ${relPropName}: ${inc.sourceModel}[];\n\n`;
    }

    output += `}\n\n`;
  }

  return output.trim() + "\n";
}
