import type { Node, Edge } from "@xyflow/react";
import type { TableNodeData } from "./convert";
import {
  decodeSourceColumnHandleId,
  decodeTargetColumnHandleId,
} from './handleUtils';

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

type ProcessedRelation = {
  targetModel: string;
  targetField: string;
  relationName: string;
};

function relationKey(nodeId: string, columnName: string): string {
  return `${nodeId.length}:${nodeId}${columnName}`;
}

function uniqueRelationFieldName(
  usedNames: Set<string>,
  baseName: string,
  relationName: string,
): string {
  let candidate = baseName;
  let collision = 1;
  while (usedNames.has(candidate)) {
    candidate = `${baseName}_${relationName}${collision === 1 ? '' : `_${collision}`}`;
    collision += 1;
  }
  usedNames.add(candidate);
  return candidate;
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

  // To build relations, we need to know which fields are foreign keys.
  // Prisma relations require a field on both sides if we want back-relations,
  // but let's just generate the minimal required relations.
  const incomingRelationsByNode = new Map<string, Array<{ relationName: string, sourceModel: string, sourceField: string, isUnique: boolean }>>();
  const relationsBySourceField = new Map<string, ProcessedRelation[]>();

  // Cache pk lookup for O(1) checks
  const pkColumnsByNode = new Map<string, Set<string>>();
  const columnsByNode = new Map<string, Set<string>>();
  for (const n of nodes) {
    const pks = new Set<string>();
    const columns = new Set<string>();
    for (const c of n.data.columns) {
      columns.add(c.column_name);
      if (c.is_pk) pks.add(c.column_name);
    }
    pkColumnsByNode.set(n.id, pks);
    columnsByNode.set(n.id, columns);
  }

  for (const edge of edges) {
    const sourceNode = nodesById.get(edge.source);
    const targetNode = nodesById.get(edge.target);
    if (!sourceNode || !targetNode) continue;

    const relName = sanitizeName(String(edge.label || `${sourceNode.data.title}_${targetNode.data.title}`));

    if (!edge.sourceHandle && !edge.targetHandle) {
      continue;
    }

    const sourceField = decodeSourceColumnHandleId(edge.sourceHandle);
    const targetField = decodeTargetColumnHandleId(edge.targetHandle);
    if (
      sourceField === null
      || targetField === null
      || !columnsByNode.get(edge.source)?.has(sourceField)
      || !columnsByNode.get(edge.target)?.has(targetField)
    ) continue;

    const isUnique = pkColumnsByNode.get(edge.source)?.has(sourceField) || false;

    const relList = incomingRelationsByNode.get(edge.target) || [];
    relList.push({
      relationName: relName,
      sourceModel: sanitizeName(sourceNode.data.title),
      sourceField: sanitizeName(sourceField),
      isUnique
    });
    incomingRelationsByNode.set(edge.target, relList);

    const sourceKey = relationKey(edge.source, sourceField);
    const sourceRelations = relationsBySourceField.get(sourceKey) || [];
    sourceRelations.push({
      targetModel: sanitizeName(targetNode.data.title),
      targetField: sanitizeName(targetField),
      relationName: relName
    });
    relationsBySourceField.set(sourceKey, sourceRelations);
  }

  for (const node of nodes) {
    const modelName = sanitizeName(node.data.title);
    const relationFieldNames = new Set<string>();
    output += `model ${modelName} {\n`;

    for (const col of node.data.columns) {
      const fieldName = sanitizeName(col.column_name);
      const prismaType = mapToPrismaType(col.data_type);

      let attributes = "";
      const isColUnique = col.column_name === 'email';
      if (col.is_pk) {
        attributes += " @id";
        if (prismaType === "Int" && col.data_type.toLowerCase().includes("serial")) {
          attributes += " @default(autoincrement())";
        } else if (prismaType === "String" && col.data_type.toLowerCase().includes("uuid")) {
          attributes += " @default(uuid())";
        }
      } else if (isColUnique) {
        attributes += " @unique";
      }

      const optional = col.is_not_null ? "" : "?";

      const relationDef = (relationsBySourceField.get(relationKey(node.id, col.column_name)) || [])
        .map((relation) => {
          const relField = uniqueRelationFieldName(
            relationFieldNames,
            `${relation.targetModel}_${fieldName}`,
            relation.relationName,
          );
          return `\n  ${relField} ${relation.targetModel}${optional} @relation("${relation.relationName}", fields: [${fieldName}], references: [${relation.targetField}])`;
        })
        .join('');

      output += `  ${fieldName} ${prismaType}${optional}${attributes}${relationDef}\n`;
    }

    // Add back-relations
    const incoming = incomingRelationsByNode.get(node.id) || [];
    for (const inc of incoming) {
      const typeSuffix = inc.isUnique ? "?" : "[]";
      const relationField = uniqueRelationFieldName(
        relationFieldNames,
        `${inc.sourceModel}_${inc.sourceField}`,
        inc.relationName,
      );
      output += `  ${relationField} ${inc.sourceModel}${typeSuffix} @relation("${inc.relationName}")\n`;
    }



    output += `}\n\n`;
  }

  return output.trim() + "\n";
}
