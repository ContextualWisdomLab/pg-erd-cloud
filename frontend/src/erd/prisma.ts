import type { Node, Edge } from "@xyflow/react";
import type { TableNodeData } from "./convert";
import { sanitizeHandleId } from "./handleUtils";

type TableColumn = TableNodeData["columns"][number];

type NodeColumnIndex = {
  byName: Map<string, TableColumn>;
  byHandle: Map<string, TableColumn>;
};

type RelationEdgeInfo = {
  targetModel: string;
  sourceField: string;
  targetField: string;
  relationName: string;
};

function columnForHandle(
  handle: string | null | undefined,
  prefix: "src-" | "tgt-",
  index: NodeColumnIndex,
): TableColumn | undefined {
  if (!handle?.startsWith(prefix)) {
    return undefined;
  }
  const identifier = handle.slice(prefix.length);
  return index.byHandle.get(identifier) ?? index.byName.get(identifier);
}

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
  const columnsByNodeId = new Map<string, NodeColumnIndex>();
  for (const n of nodes) {
    nodesById.set(n.id, n);
    const byName = new Map<string, TableColumn>();
    const byHandle = new Map<string, TableColumn>();
    for (const column of n.data.columns) {
      byName.set(column.column_name, column);
      byHandle.set(sanitizeHandleId(column.column_name), column);
    }
    columnsByNodeId.set(n.id, { byName, byHandle });
  }

  // To build relations, we need to know which fields are foreign keys.
  // Prisma relations require a field on both sides if we want back-relations,
  // but let's just generate the minimal required relations.
  const fkNodeColumnPairs = new Set<string>();
  const fkNodesWithoutHandles = new Set<string>();
  const incomingRelationsByNode = new Map<string, Array<{ relationName: string, sourceModel: string, sourceField: string, isUnique: boolean }>>();
  const outgoingRelationsByNode = new Map<
    string,
    Map<string, RelationEdgeInfo[]>
  >();

  for (const edge of edges) {
    const sourceNode = nodesById.get(edge.source);
    const targetNode = nodesById.get(edge.target);
    const sourceColumns = columnsByNodeId.get(edge.source);
    const targetColumns = columnsByNodeId.get(edge.target);
    if (!sourceNode || !targetNode || !sourceColumns || !targetColumns) continue;

    const relName = sanitizeName(String(edge.label || `${sourceNode.data.title}_${targetNode.data.title}`));

    const sourceColumn = columnForHandle(edge.sourceHandle, "src-", sourceColumns);
    const sourceField = sourceColumn?.column_name ?? "";
    if (sourceColumn) {
      fkNodeColumnPairs.add(`${edge.source}:${sourceField}`);
    } else if (!edge.sourceHandle) {
      fkNodesWithoutHandles.add(edge.source);
    }

    const targetColumn = columnForHandle(edge.targetHandle, "tgt-", targetColumns);
    const targetField = targetColumn?.column_name ?? "id";

    if (sourceField) {
      const isUnique = sourceColumn?.is_pk ?? false;
      const normalizedSourceField = sanitizeName(sourceField);

      const relList = incomingRelationsByNode.get(edge.target) || [];
      relList.push({
        relationName: relName,
        sourceModel: sanitizeName(sourceNode.data.title),
        sourceField: normalizedSourceField,
        isUnique
      });
      incomingRelationsByNode.set(edge.target, relList);

      let relationsByField = outgoingRelationsByNode.get(edge.source);
      if (!relationsByField) {
        relationsByField = new Map<string, RelationEdgeInfo[]>();
        outgoingRelationsByNode.set(edge.source, relationsByField);
      }
      const outgoing = relationsByField.get(sourceField) || [];
      outgoing.push({
        targetModel: sanitizeName(targetNode.data.title),
        sourceField: normalizedSourceField,
        targetField: sanitizeName(targetField),
        relationName: relName
      });
      relationsByField.set(sourceField, outgoing);
    }
  }

  for (const node of nodes) {
    const modelName = sanitizeName(node.data.title);
    output += `model ${modelName} {\n`;

    let hasId = false;
    const emittedRelationFields = new Set<string>();

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
      let relationDefs = "";
      const outgoing = outgoingRelationsByNode.get(node.id)?.get(col.column_name) || [];
      for (const edgeInfo of outgoing) {
        let relField = sanitizeName(edgeInfo.targetModel) + "_" + fieldName;
        if (emittedRelationFields.has(relField)) {
          relField += "_" + sanitizeName(edgeInfo.relationName);
        }
        emittedRelationFields.add(relField);
        relationDefs += `\n  ${relField} ${edgeInfo.targetModel}${optional} @relation("${edgeInfo.relationName}", fields: [${edgeInfo.sourceField}], references: [${edgeInfo.targetField}])`;
      }

      output += `  ${fieldName} ${prismaType}${optional}${attributes}${relationDefs}\n`;
    }

    // Add back-relations
    const incoming = incomingRelationsByNode.get(node.id) || [];
    const emittedBackRelationFields = new Set<string>();
    for (const inc of incoming) {
      const typeSuffix = inc.isUnique ? "?" : "[]";
      let relationField = `${inc.sourceModel}_${inc.sourceField}`;
      if (emittedBackRelationFields.has(relationField)) {
        relationField += `_${sanitizeName(inc.relationName)}`;
      }
      emittedBackRelationFields.add(relationField);
      output += `  ${relationField} ${inc.sourceModel}${typeSuffix} @relation("${inc.relationName}")\n`;
    }



    output += `}\n\n`;
  }

  return output.trim() + "\n";
}
