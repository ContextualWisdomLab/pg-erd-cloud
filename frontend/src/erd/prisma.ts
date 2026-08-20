import type { Node, Edge } from "@xyflow/react";
import type { TableNodeData } from "./convert";
import {
  sourceColumnHandleId,
  targetColumnHandleId,
} from "./handleUtils";

const PRISMA_RESERVED_WORDS = ["datasource", "generator", "model", "enum"];

function sanitizeName(name: string): string {
  // Prisma model and field names must start with a letter and contain only alphanumeric characters and underscores
  let sanitized = name.replace(/[^a-zA-Z0-9_]/g, "_");
  if (!/^[a-zA-Z]/.test(sanitized)) {
    sanitized = "M_" + sanitized;
  }

  if (PRISMA_RESERVED_WORDS.includes(sanitized.toLowerCase())) {
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

type RelationInfo = {
  targetModel: string;
  targetFields: string[];
  relationName: string;
  sourceModel: string;
  sourceField: string;
  isUnique: boolean;
};

function columnNameFromHandle(
  node: Node<TableNodeData>,
  handle: string | null | undefined,
  prefix: string,
  makeHandle: (columnName: string) => string,
): string | null {
  if (!handle?.startsWith(prefix)) return null;

  const actualColumn = node.data.columns.find(
    (column) => makeHandle(column.column_name) === handle,
  )?.column_name;
  if (actualColumn) return actualColumn;

  // Keep diagrams saved before encoded handle IDs backwards compatible.
  const legacyColumn = handle.slice(prefix.length);
  return node.data.columns.find(
    (column) => column.column_name === legacyColumn,
  )?.column_name ?? null;
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
  const incomingRelationsByNode = new Map<string, RelationInfo[]>();
  const outgoingRelationsByModelField = new Map<string, RelationInfo[]>();

  for (const edge of edges) {
    const sourceNode = nodesById.get(edge.source);
    const targetNode = nodesById.get(edge.target);
    if (!sourceNode || !targetNode) continue;

    const relName = sanitizeName(String(edge.label || `${sourceNode.data.title}_${targetNode.data.title}`));

    const sourceField = columnNameFromHandle(
      sourceNode,
      edge.sourceHandle,
      "src-",
      sourceColumnHandleId,
    );
    if (sourceField) {
      fkNodeColumnPairs.add(`${edge.source}:${sourceField}`);
    } else if (!edge.sourceHandle) {
      fkNodesWithoutHandles.add(edge.source);
    }

    const targetField =
      columnNameFromHandle(
        targetNode,
        edge.targetHandle,
        "tgt-",
        targetColumnHandleId,
      ) ?? "id";

    if (sourceField) {
      const isUnique = sourceNode.data.columns.find(c => c.column_name === sourceField)?.is_pk || false;

      const relList = incomingRelationsByNode.get(edge.target) || [];
      const relation: RelationInfo = {
        relationName: relName,
        sourceModel: sanitizeName(sourceNode.data.title),
        sourceField: sanitizeName(sourceField),
        isUnique,
        targetModel: sanitizeName(targetNode.data.title),
        targetFields: [sanitizeName(targetField)],
      };
      if (!relList.some((item) =>
        item.relationName === relation.relationName &&
        item.sourceModel === relation.sourceModel &&
        item.sourceField === relation.sourceField
      )) {
        relList.push(relation);
      }
      incomingRelationsByNode.set(edge.target, relList);

      const relationKey = `${sanitizeName(sourceNode.data.title)}:${sanitizeName(sourceField)}`;
      const outgoing = outgoingRelationsByModelField.get(relationKey) || [];
      if (!outgoing.some((item) =>
        item.relationName === relation.relationName &&
        item.targetModel === relation.targetModel &&
        item.targetFields[0] === relation.targetFields[0]
      )) {
        outgoing.push(relation);
      }
      outgoingRelationsByModelField.set(relationKey, outgoing);
    }
  }

  for (const node of nodes) {
    const modelName = sanitizeName(node.data.title);
    output += `model ${modelName} {\n`;

    let hasId = false;

    for (const col of node.data.columns) {
      const fieldName = sanitizeName(col.column_name);

      const isFk =
        fkNodeColumnPairs.has(`${node.id}:${col.column_name}`) ||
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
      const edgeInfos = outgoingRelationsByModelField.get(`${modelName}:${fieldName}`) || [];
      const relationDef = edgeInfos.map((edgeInfo, index) => {
        const suffix = index === 0 ? "" : `_${index + 1}`;
        const relField = `${sanitizeName(edgeInfo.targetModel)}_${fieldName}${suffix}`;
        return `\n  ${relField} ${edgeInfo.targetModel}${optional} @relation("${edgeInfo.relationName}", fields: [${fieldName}], references: [${edgeInfo.targetFields[0]}])`;
      }).join("");

      output += `  ${fieldName} ${prismaType}${optional}${attributes}${relationDef}\n`;
    }

    // Add back-relations
    const incoming = incomingRelationsByNode.get(node.id) || [];
    const usedRelationFields = new Set<string>();
    for (const inc of incoming) {
      const typeSuffix = inc.isUnique ? "?" : "[]";
      const baseField = `${inc.sourceModel}_${inc.sourceField}`;
      let relationField = baseField;
      let suffix = 2;
      while (usedRelationFields.has(relationField)) {
        relationField = `${baseField}_${suffix}`;
        suffix += 1;
      }
      usedRelationFields.add(relationField);
      output += `  ${relationField} ${inc.sourceModel}${typeSuffix} @relation("${inc.relationName}")\n`;
    }



    output += `}\n\n`;
  }

  return output.trim() + "\n";
}
