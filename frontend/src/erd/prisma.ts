import type { Node, Edge } from "@xyflow/react";
import type { TableNodeData } from "./convert";
import { decodeSourceColumnHandleId, decodeTargetColumnHandleId } from "./handleUtils";

function sanitizeName(name: string): string {
  // Prisma model and field names must start with a letter and contain only alphanumeric characters and underscores
  let sanitized = name.replace(/[^a-zA-Z0-9_]/g, "_");
  if (!/^[a-zA-Z]/.test(sanitized)) {
    sanitized = "M_" + sanitized;
  }
  return sanitized;
}

function mapToPrismaType(pgType: string): string {
  const t = pgType.toLowerCase();

  if (t.includes("int") || t.includes("serial")) {
    return "Int";
  }
  if (t.includes("char") || t.includes("text") || t.includes("uuid")) {
    return "String";
  }
  if (t.includes("bool")) {
    return "Boolean";
  }
  if (t.includes("time") || t.includes("date")) {
    return "DateTime";
  }
  if (t.includes("float") || t.includes("double") || t.includes("numeric") || t.includes("real") || t.includes("decimal")) {
    return "Float";
  }
  if (t.includes("json")) {
    return "Json";
  }
  if (t.includes("bytea")) {
    return "Bytes";
  }
  return "String"; // fallback
}

export function exportPrisma(
  nodes: Node<TableNodeData>[],
  edges: Edge[],
): string {
  if (nodes.length === 0) {
    return "// No tables to export\n";
  }

  let output = `// Prisma schema generated from ERD\ngenerator client {\n  provider = "prisma-client-js"\n}\n\ndatasource db {\n  provider = "postgresql"\n  url      = env("DATABASE_URL")\n}\n\n`;

  const nodesById = new Map<string, Node<TableNodeData>>();
  for (const n of nodes) {
    nodesById.set(n.id, n);
  }

  type RelationInfo = {
    sourceModel: string;
    targetModel: string;
    sourceFields: string[];
    targetFields: string[];
    relationName: string;
  };
  const incomingRelationsByNode = new Map<string, Array<{
    relationName: string;
    sourceModel: string;
    sourceField: string;
    isUnique: boolean;
  }>>();
  const relationsBySourceField = new Map<string, RelationInfo[]>();
  const pkColumnsByNode = new Map<string, Set<string>>();
  const columnNamesByNode = new Map<string, Set<string>>();
  const allocatedRelationNames = new Set<string>();
  for (const node of nodes) {
    const pks = new Set<string>();
    const columnNames = new Set<string>();
    for (const column of node.data.columns || []) {
      columnNames.add(column.column_name);
      if (column.is_pk) pks.add(column.column_name);
    }
    pkColumnsByNode.set(node.id, pks);
    columnNamesByNode.set(node.id, columnNames);
  }

  for (const edge of edges) {
    const sourceNode = nodesById.get(edge.source);
    const targetNode = nodesById.get(edge.target);
    if (!sourceNode || !targetNode || !edge.sourceHandle || !edge.targetHandle) continue;

    const sourceField = decodeSourceColumnHandleId(edge.sourceHandle);
    const targetField = decodeTargetColumnHandleId(edge.targetHandle);
    if (
      sourceField === null ||
      targetField === null ||
      !columnNamesByNode.get(edge.source)?.has(sourceField) ||
      !columnNamesByNode.get(edge.target)?.has(targetField)
    ) {
      continue;
    }

    const relationNameBase = sanitizeName(
      String(edge.label || `${sourceNode.data.title}_${targetNode.data.title}`),
    );
    let relationName = relationNameBase;
    let suffix = 2;
    while (allocatedRelationNames.has(relationName)) {
      relationName = `${relationNameBase}_${suffix}`;
      suffix += 1;
    }
    allocatedRelationNames.add(relationName);
    const sourceModel = sanitizeName(sourceNode.data.title);
    const targetModel = sanitizeName(targetNode.data.title);
    const sanitizedSourceField = sanitizeName(sourceField);
    const relationInfo: RelationInfo = {
      sourceModel,
      targetModel,
      sourceFields: [sanitizedSourceField],
      targetFields: [sanitizeName(targetField)],
      relationName,
    };
    const relationKey = `${edge.source}:${sanitizedSourceField}`;
    const relations = relationsBySourceField.get(relationKey);
    if (relations) {
      relations.push(relationInfo);
    } else {
      relationsBySourceField.set(relationKey, [relationInfo]);
    }

    const incoming = incomingRelationsByNode.get(edge.target) || [];
    incoming.push({
      relationName,
      sourceModel,
      sourceField: sanitizedSourceField,
      isUnique: pkColumnsByNode.get(edge.source)?.has(sourceField) || false,
    });
    incomingRelationsByNode.set(edge.target, incoming);
  }

  for (const node of nodes) {
    const modelName = sanitizeName(node.data.title);
    output += `model ${modelName} {\n`;

    let hasId = false;

    for (const col of node.data.columns) {
      const fieldName = sanitizeName(col.column_name);

      const edgeInfos = relationsBySourceField.get(`${node.id}:${fieldName}`) || [];
      const prismaType = mapToPrismaType(col.data_type);

      let attributes = "";
      const isColUnique = col.column_name === 'email';
      if (col.is_pk) {
        attributes += " @id";
        hasId = true;
        if (prismaType === "Int" && col.data_type.toLowerCase().includes("serial")) {
          attributes += " @default(autoincrement())";
        } else if (prismaType === "String" && col.data_type.toLowerCase().includes("uuid")) {
          attributes += " @default(uuid())";
        }
      } else if (isColUnique) {
        attributes += " @unique";
      }

      const optional = col.is_not_null ? "" : "?";

      let relationDef = "";
      for (const edgeInfo of edgeInfos) {
        const baseRelationField = sanitizeName(edgeInfo.targetModel) + "_" + fieldName;
        const relationField = edgeInfos.length === 1
          ? baseRelationField
          : sanitizeName(`${baseRelationField}_${edgeInfo.relationName}`);
        relationDef += `\n  ${relationField} ${edgeInfo.targetModel}${optional} @relation("${edgeInfo.relationName}", fields: [${fieldName}], references: [${edgeInfo.targetFields[0]}])`;
      }

      output += `  ${fieldName} ${prismaType}${optional}${attributes}${relationDef}\n`;
    }

    // Add back-relations
    const incoming = incomingRelationsByNode.get(node.id) || [];
    const incomingBaseCounts = new Map<string, number>();
    for (const relation of incoming) {
      const base = `${relation.sourceModel}_${relation.sourceField}`;
      incomingBaseCounts.set(base, (incomingBaseCounts.get(base) || 0) + 1);
    }
    for (const inc of incoming) {
      const typeSuffix = inc.isUnique ? "?" : "[]";
      const baseField = `${inc.sourceModel}_${inc.sourceField}`;
      const relationField = (incomingBaseCounts.get(baseField) || 0) === 1
        ? baseField
        : sanitizeName(`${baseField}_${inc.relationName}`);
      output += `  ${relationField} ${inc.sourceModel}${typeSuffix} @relation("${inc.relationName}")\n`;
    }



    output += `}\n\n`;
  }

  return output.trim() + "\n";
}
