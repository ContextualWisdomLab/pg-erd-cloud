import type { Node, Edge } from "@xyflow/react";
import type { TableNodeData } from "./convert";
import {
  sanitizeHandleId,
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

function columnNameFromHandle(
  columns: TableNodeData["columns"],
  handle: string | null | undefined,
  prefix: string,
  makeHandle: (columnName: string) => string,
): string | undefined {
  if (!handle?.startsWith(prefix)) return undefined;

  const column = columns.find((candidate) => makeHandle(candidate.column_name) === handle);
  if (column) return column.column_name;

  // Keep accepting diagrams created before handles were encoded.
  const legacyColumnName = handle.slice(prefix.length);
  return columns.some((column) => column.column_name === legacyColumnName)
    ? legacyColumnName
    : undefined;
}

type OutgoingRelation = {
  targetModel: string;
  targetField: string;
  relationName: string;
};

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
  const outgoingRelationsByModelField = new Map<string, Map<string, OutgoingRelation>>();

  for (const edge of edges) {
    const sourceNode = nodesById.get(edge.source);
    const targetNode = nodesById.get(edge.target);
    if (!sourceNode || !targetNode) continue;

    const relName = sanitizeName(String(edge.label || `${sourceNode.data.title}_${targetNode.data.title}`));

    const sourceField = columnNameFromHandle(
      sourceNode.data.columns,
      edge.sourceHandle,
      "src-",
      sourceColumnHandleId,
    );
    if (sourceField) {
      fkNodeColumnPairs.add(`${edge.source}:${sanitizeHandleId(sourceField)}`);
    } else if (!edge.sourceHandle) {
      fkNodesWithoutHandles.add(edge.source);
    }

    const targetField =
      columnNameFromHandle(
        targetNode.data.columns,
        edge.targetHandle,
        "tgt-",
        targetColumnHandleId,
      ) || "id";

    if (sourceField) {
      const sourceModel = sanitizeName(sourceNode.data.title);
      const sourceFieldName = sanitizeName(sourceField);
      let outgoingByField = outgoingRelationsByModelField.get(sourceModel);
      if (!outgoingByField) {
        outgoingByField = new Map();
        outgoingRelationsByModelField.set(sourceModel, outgoingByField);
      }
      if (outgoingByField.has(sourceFieldName)) continue;

      outgoingByField.set(sourceFieldName, {
        targetModel: sanitizeName(targetNode.data.title),
        targetField: sanitizeName(targetField),
        relationName: relName,
      });

      const isUnique = sourceNode.data.columns.find(c => c.column_name === sourceField)?.is_pk || false;

      const relList = incomingRelationsByNode.get(edge.target) || [];
      relList.push({
        relationName: relName,
        sourceModel,
        sourceField: sourceFieldName,
        isUnique
      });
      incomingRelationsByNode.set(edge.target, relList);
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
      const edgeInfo = outgoingRelationsByModelField.get(modelName)?.get(fieldName);
      if (edgeInfo) {
        // This field is a foreign key, but in Prisma, we typically define the relation object field
        // alongside the scalar field. We will add the relation object field here.
        const relField = sanitizeName(edgeInfo.targetModel) + "_" + fieldName;
        relationDef = `\n  ${relField} ${edgeInfo.targetModel}${optional} @relation("${edgeInfo.relationName}", fields: [${fieldName}], references: [${edgeInfo.targetField}])`;
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
