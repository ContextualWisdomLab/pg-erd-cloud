import type { Node, Edge } from "@xyflow/react";
import type { TableNodeData, ForeignKeyEdgeData } from "./convert";
import { decodeHandleId } from "./handleUtils";

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
  if (t.includes("int8") || t.includes("bigint") || t.includes("bigserial")) {
    return "string";
  }
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

function escapeLiteral(value: string): string {
  const serializedValue = JSON.stringify(value);
  if (serializedValue === undefined) {
    throw new TypeError("Unable to serialize TypeORM metadata");
  }
  return serializedValue.slice(1, -1);
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

  // Track all relationships coming INTO a target model
  const incomingRelationsByNode = new Map<string, Array<{ sourceModel: string, sourceField: string }>>();

  // Track relationship configurations for the source models
  const edgesProcessed = new Map<string, { sourceModel: string, targetModel: string, sourceFields: string[], targetFields: string[] }>();

  // Ensure unique class names
  const usedClassNames = new Map<string, string>();
  const classNamesSet = new Set<string>();

  // To ensure stable alphabetical suffixing or mapping, sort nodes by id (which are basically relation_oids).
  const sortedNodes = [...nodes].sort((a, b) => a.id.localeCompare(b.id));

  for (const node of sortedNodes) {
    let schemaName = 'public';
    let baseName = node.data.title;
    const parts = node.data.title.split('.');
    if (parts.length > 1) {
      schemaName = parts[0];
      baseName = parts.slice(1).join('.');
    }

    let candidate = sanitizeClassName(schemaName + "_" + baseName);
    let finalClassName = candidate;
    let counter = 1;
    while (classNamesSet.has(finalClassName)) {
      finalClassName = candidate + "_" + counter;
      counter++;
    }
    classNamesSet.add(finalClassName);
    usedClassNames.set(node.id, finalClassName);
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
      if (edgeData.sourceColumns.length === 0 || edgeData.sourceColumns.length !== edgeData.targetColumns.length) {
         throw new Error("Invalid composite foreign key metadata");
      }
      // Check column membership
      const srcNodeHasCols = edgeData.sourceColumns.every(col => sourceNode.data.columns.some(c => c.column_name === col));
      const tgtNodeHasCols = edgeData.targetColumns.every(col => targetNode.data.columns.some(c => c.column_name === col));
      if (!srcNodeHasCols || !tgtNodeHasCols) {
         throw new Error("Invalid composite foreign key metadata: missing columns");
      }

      sourceCols = [...edgeData.sourceColumns];
      targetCols = [...edgeData.targetColumns];

    } else {
      let sourceField = "";
      if (edge.sourceHandle?.startsWith("src-")) {
        sourceField = decodeHandleId(edge.sourceHandle);
      }

      let targetField = "id";
      if (edge.targetHandle?.startsWith("tgt-")) {
        targetField = decodeHandleId(edge.targetHandle);
      }

      if (sourceField) {
        const sourceHasColumn = sourceNode.data.columns.some(
          (column) => column.column_name === sourceField
        );
        const targetHasColumn = targetNode.data.columns.some(
          (column) => column.column_name === targetField
        );
        if (!sourceHasColumn || !targetHasColumn) {
          throw new Error("Invalid foreign key metadata: missing columns");
        }
        sourceCols = [sourceField];
        targetCols = [targetField];
      }
    }

    if (sourceCols.length > 0) {
      const relList = incomingRelationsByNode.get(edge.target) || [];
      // Combine multiple columns into a signature for naming if necessary
      const combinedSourceField = sourceCols.map(sanitizePropertyName).join("_");

      relList.push({
        sourceModel,
        sourceField: combinedSourceField
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

    output += `@Entity({ name: "${escapeLiteral(tableName)}", schema: "${escapeLiteral(schemaName)}" })\nexport class ${className} {\n`;

    for (const col of node.data.columns) {
      const propName = sanitizePropertyName(col.column_name);
      const tsType = mapToTsType(col.data_type);
      let colDecorator = "";
      if (col.is_pk) {
        if (col.data_type.toLowerCase().includes("serial")) {
          colDecorator = `@PrimaryGeneratedColumn({ name: "${escapeLiteral(col.column_name)}" })`;
        } else {
          const colOpts = [];
          colOpts.push(`name: "${escapeLiteral(col.column_name)}"`);
          if (col.data_type) colOpts.push(`type: "${escapeLiteral(col.data_type)}"`);
          colDecorator = `@PrimaryColumn({ ${colOpts.join(", ")} })`;
        }
      } else {
        const colOpts = [];
        colOpts.push(`name: "${escapeLiteral(col.column_name)}"`);
        if (!col.is_not_null) colOpts.push(`nullable: true`);
        if (col.data_type) colOpts.push(`type: "${escapeLiteral(col.data_type)}"`);
        colDecorator = `@Column({ ${colOpts.join(", ")} })`;
      }

      const optional = col.is_not_null ? "" : "?";
      output += `  ${colDecorator}\n  ${propName}${optional}: ${tsType};\n\n`;
    }

    // Add forward relations
    for (const [_, edgeInfo] of edgesProcessed) {
      if (edgeInfo.sourceModel === className) {
        const relProp = edgeInfo.targetModel.charAt(0).toLowerCase() + edgeInfo.targetModel.slice(1) + "_" + edgeInfo.sourceFields.map(sanitizePropertyName).join("_");
        output += `  @ManyToOne(() => ${edgeInfo.targetModel})\n`;
        if (edgeInfo.sourceFields.length === 1) {
            output += `  @JoinColumn({ name: "${escapeLiteral(edgeInfo.sourceFields[0])}", referencedColumnName: "${escapeLiteral(edgeInfo.targetFields[0])}" })\n`;
        } else {
            const joinColumns = edgeInfo.sourceFields.map((sourceField, index) => `{ name: "${escapeLiteral(sourceField)}", referencedColumnName: "${escapeLiteral(edgeInfo.targetFields[index])}" }`).join(", ");
            output += `  @JoinColumn([${joinColumns}])\n`;
        }
        output += `  ${relProp}?: ${edgeInfo.targetModel};\n\n`;
      }
    }

    // Add back relations
    const incoming = incomingRelationsByNode.get(node.id) || [];
    for (const inc of incoming) {
      const sourcePropLower = inc.sourceModel.charAt(0).toLowerCase() + inc.sourceModel.slice(1);
      const relPropName = sourcePropLower + "s_" + inc.sourceField;
      const childRelationProp = className.charAt(0).toLowerCase() + className.slice(1) + "_" + inc.sourceField;
      output += `  @OneToMany(() => ${inc.sourceModel}, (e) => e.${childRelationProp})
  ${relPropName}: ${inc.sourceModel}[];

`;
    }

    output += `}\n\n`;
  }

  return output.trim() + "\n";
}
