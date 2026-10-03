import type { Node, Edge } from "@xyflow/react";
import type { TableNodeData } from "./convert";
import { sanitizeHandleId } from "./handleUtils";

function sanitizeName(name: string): string {
  // Prisma model and field names must start with a letter and contain only alphanumeric characters and underscores
  let sanitized = name.replace(/[^a-zA-Z0-9_]/g, "_");
  if (!/^[a-zA-Z]/.test(sanitized)) {
    sanitized = "M_" + sanitized;
  }
  return sanitized;
}

function mapToPrismaType(pgType: string, isFk: boolean): string {
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

  // To build relations, we need to know which fields are foreign keys.
  // Prisma relations require a field on both sides if we want back-relations,
  // but let's just generate the minimal required relations.
  const fkNodeColumnPairs = new Set<string>();
  const fkNodesWithoutHandles = new Set<string>();
  const incomingRelationsByNode = new Map<string, Array<{ relationName: string, sourceModel: string, sourceField: string, isUnique: boolean }>>();
  // ⚡ Bolt: Prevent O(N * C * E) generation by pre-computing relation lookups
  const outgoingRelationsByKey = new Map<string, { targetModel: string, targetField: string, relationName: string }>();

  // Pre-compute columns for faster exact column and unique constraint matching without iterating over all columns
  const nodeColumnIndices = new Map<string, Map<string, { column_name: string, is_pk: boolean, data_type: string }>>();
  for (const node of nodes) {
    const colMap = new Map();
    for (const col of node.data.columns) {
      colMap.set(col.column_name, col);
    }
    nodeColumnIndices.set(node.id, colMap);
  }

  for (const edge of edges) {
    const sourceNode = nodesById.get(edge.source);
    const targetNode = nodesById.get(edge.target);
    if (!sourceNode || !targetNode) continue;

    const relName = sanitizeName(String(edge.label || `${sourceNode.data.title}_${targetNode.data.title}`));

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
      // Use the O(1) map we pre-computed instead of the O(C) array .find()
      const isUnique = nodeColumnIndices.get(sourceNode.id)?.get(sourceField)?.is_pk || false;

      const relList = incomingRelationsByNode.get(edge.target) || [];
      relList.push({
        relationName: relName,
        sourceModel: sanitizeName(sourceNode.data.title),
        sourceField: sanitizeName(sourceField),
        isUnique
      });
      incomingRelationsByNode.set(edge.target, relList);

      const sourceModelName = sanitizeName(sourceNode.data.title);
      // We index by the canonical target handle/column instead of raw string if it differs
      const targetColumn = nodeColumnIndices.get(targetNode.id)?.get(targetField) ? sanitizeName(targetField) : sanitizeName(targetField);

      const sourceFieldName = sanitizeName(sourceField);
      outgoingRelationsByKey.set(`${sourceModelName}:${sourceFieldName}`, {
        targetModel: sanitizeName(targetNode.data.title),
        targetField: targetColumn,
        relationName: relName
      });
    }
  }

  for (const node of nodes) {
    const modelName = sanitizeName(node.data.title);
    output += `model ${modelName} {\n`;

    let hasId = false;

    for (const col of node.data.columns) {
      const fieldName = sanitizeName(col.column_name);

      const isFk =
        fkNodeColumnPairs.has(`${node.id}:${sanitizeHandleId(col.column_name)}`) ||
        (fkNodesWithoutHandles.has(node.id) && node.data.badges?.fk);

      const prismaType = mapToPrismaType(col.data_type, isFk);

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

      // Determine if there is a relation defined on this field
      let relationDef = "";
      const relInfo = outgoingRelationsByKey.get(`${modelName}:${fieldName}`);
      if (relInfo) {
        const relField = sanitizeName(relInfo.targetModel) + "_" + fieldName;
        relationDef = `\n  ${relField} ${relInfo.targetModel}${optional} @relation("${relInfo.relationName}", fields: [${fieldName}], references: [${relInfo.targetField}])`;
      }

      output += `  ${fieldName} ${prismaType}${optional}${attributes}${relationDef}\n`;
    }

    // Add back-relations
    const incoming = incomingRelationsByNode.get(node.id) || [];
    for (const inc of incoming) {
      const typeSuffix = inc.isUnique ? "?" : "[]";
      output += `  ${inc.sourceModel}_${inc.sourceField} ${inc.sourceModel}${typeSuffix} @relation("${inc.relationName}")\n`;
    }



    output += `}\n\n`;
  }

  return output.trim() + "\n";
}
