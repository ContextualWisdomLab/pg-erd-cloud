import type { Edge, Node } from "@xyflow/react";
import type { TableNodeData, ForeignKeyEdgeData } from "./convert";
import { sourceColumnHandleId, targetColumnHandleId } from "./handleUtils";
import {
  allocatePrismaIdentifiers,
  buildPrismaManifest,
  preferredPrismaName,
  type PrismaIdentifierMapping,
  type PrismaIdentifierRequest,
} from "./prismaIdentifiers";

export const PRISMA_EXPORT_FAILURE_MESSAGE =
  "Prisma 식별자를 고유하게 할당하지 못했습니다. 진단 매니페스트를 받은 뒤 테이블·컬럼 이름을 바꾼 다음 다시 내보내세요.";

export const PRISMA_EXPORT_FAILURE_SCHEMA = `// Prisma export failed.
// A unique identifier could not be allocated within the configured bound.
// Download the diagnostic manifest, rename colliding tables or columns, then export again.
`;

export type PrismaExportManifest = {
  contractVersion: string;
  mappings: PrismaIdentifierMapping[];
};

export type PrismaExportDocument = {
  ok: boolean;
  schema: string;
  manifest: PrismaExportManifest;
};

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
  if (
    t.includes("float") ||
    t.includes("double") ||
    t.includes("numeric") ||
    t.includes("real") ||
    t.includes("decimal")
  ) {
    return "Float";
  }
  if (t.includes("json")) {
    return "Json";
  }
  if (t.includes("bytea")) {
    return "Bytes";
  }
  return "String";
}

function compareNodes(
  left: Node<TableNodeData>,
  right: Node<TableNodeData>,
): number {
  const titleOrder = left.data.title.localeCompare(right.data.title);
  if (titleOrder !== 0) {
    return titleOrder;
  }
  return left.id.localeCompare(right.id);
}

function resolveFkColumns(
  edge: Edge,
  sourceNode: Node<TableNodeData>,
  targetNode: Node<TableNodeData>,
): { sourceColumns: string[]; targetColumns: string[] } | null {
  const data = edge.data as ForeignKeyEdgeData | undefined;
  const mappedSource = data?.sourceColumns?.filter(Boolean) ?? [];
  const mappedTarget = data?.targetColumns?.filter(Boolean) ?? [];
  if (mappedSource.length > 0 && mappedSource.length === mappedTarget.length) {
    return { sourceColumns: mappedSource, targetColumns: mappedTarget };
  }

  const sourceFromHandle = (sourceNode.data.columns || []).find(
    (column) => sourceColumnHandleId(column.column_name) === edge.sourceHandle,
  )?.column_name;
  const targetFromHandle = (targetNode.data.columns || []).find(
    (column) => targetColumnHandleId(column.column_name) === edge.targetHandle,
  )?.column_name;
  if (sourceFromHandle && targetFromHandle) {
    return {
      sourceColumns: [sourceFromHandle],
      targetColumns: [targetFromHandle],
    };
  }

  if (
    edge.sourceHandle?.startsWith("src-") &&
    !edge.sourceHandle.startsWith("src-c-")
  ) {
    const legacySource = edge.sourceHandle.slice(4);
    const legacyTarget =
      edge.targetHandle?.startsWith("tgt-") &&
      !edge.targetHandle.startsWith("tgt-c-")
        ? edge.targetHandle.slice(4)
        : "id";
    if (
      sourceNode.data.columns.some((column) => column.column_name === legacySource)
    ) {
      return {
        sourceColumns: [legacySource],
        targetColumns: [legacyTarget],
      };
    }
  }

  return null;
}

function quotePrismaString(value: string): string {
  return JSON.stringify(value);
}

function mapAttribute(source: string, generated: string): string {
  return source === generated ? "" : ` @map(${quotePrismaString(source)})`;
}

/**
 * Build a Prisma schema and the source→generated identifier manifest.
 */
export function exportPrismaDocument(
  nodes: Node<TableNodeData>[],
  edges: Edge[],
  options?: { maxAttempts?: number },
): PrismaExportDocument {
  const emptyManifest = buildPrismaManifest([]);
  if (nodes.length === 0) {
    return {
      ok: true,
      schema: "// No tables to export\n",
      manifest: emptyManifest,
    };
  }

  const nodesById = new Map<string, Node<TableNodeData>>();
  for (const node of nodes) {
    nodesById.set(node.id, node);
  }

  const modelRequests: PrismaIdentifierRequest[] = nodes.map((node) => ({
    key: `model:${node.id}`,
    kind: "model",
    namespace: "models",
    source: node.data.title,
  }));
  const modelAllocation = allocatePrismaIdentifiers(
    modelRequests,
    options?.maxAttempts,
  );
  if (!modelAllocation.ok) {
    return {
      ok: false,
      schema: PRISMA_EXPORT_FAILURE_SCHEMA,
      manifest: buildPrismaManifest(modelAllocation.mappings),
    };
  }

  const fieldRequests: PrismaIdentifierRequest[] = [];
  for (const node of nodes) {
    const modelName = modelAllocation.names.get(`model:${node.id}`);
    if (!modelName) {
      continue;
    }
    for (const column of node.data.columns) {
      fieldRequests.push({
        key: `field:${node.id}:${column.column_name}`,
        kind: "field",
        namespace: `fields:${modelName}`,
        source: column.column_name,
      });
    }
  }

  const resolvedEdges: Array<{
    edge: Edge;
    sourceNode: Node<TableNodeData>;
    targetNode: Node<TableNodeData>;
    sourceColumns: string[];
    targetColumns: string[];
    relationSource: string;
  }> = [];
  const sortedEdges = [...edges].sort((left, right) =>
    left.id.localeCompare(right.id),
  );
  for (const edge of sortedEdges) {
    const sourceNode = nodesById.get(edge.source);
    const targetNode = nodesById.get(edge.target);
    if (!sourceNode || !targetNode) {
      continue;
    }
    const columns = resolveFkColumns(edge, sourceNode, targetNode);
    if (!columns) {
      continue;
    }
    resolvedEdges.push({
      edge,
      sourceNode,
      targetNode,
      sourceColumns: columns.sourceColumns,
      targetColumns: columns.targetColumns,
      relationSource: String(
        edge.label || `${sourceNode.data.title}_${targetNode.data.title}`,
      ),
    });
  }

  const relationRequests: PrismaIdentifierRequest[] = resolvedEdges.map(
    (item) => ({
      key: `relation:${item.edge.id}`,
      kind: "relation",
      namespace: "relations",
      source: item.relationSource,
    }),
  );
  const relationAllocation = allocatePrismaIdentifiers(
    relationRequests,
    options?.maxAttempts,
  );
  if (!relationAllocation.ok) {
    return {
      ok: false,
      schema: PRISMA_EXPORT_FAILURE_SCHEMA,
      manifest: buildPrismaManifest([
        ...modelAllocation.mappings,
        ...relationAllocation.mappings,
      ]),
    };
  }

  for (const item of resolvedEdges) {
    const sourceModel = modelAllocation.names.get(`model:${item.sourceNode.id}`);
    const targetModel = modelAllocation.names.get(`model:${item.targetNode.id}`);
    if (!sourceModel || !targetModel) {
      continue;
    }
    const sourceField = preferredPrismaName(item.sourceColumns[0] ?? "id");
    fieldRequests.push({
      key: `relfield:${item.edge.id}:forward`,
      kind: "field",
      namespace: `fields:${sourceModel}`,
      source: `${targetModel}_${sourceField}`,
    });
    fieldRequests.push({
      key: `relfield:${item.edge.id}:back`,
      kind: "field",
      namespace: `fields:${targetModel}`,
      source: `${sourceModel}_${sourceField}`,
    });
  }

  const fieldAllocation = allocatePrismaIdentifiers(
    fieldRequests,
    options?.maxAttempts,
  );
  if (!fieldAllocation.ok) {
    return {
      ok: false,
      schema: PRISMA_EXPORT_FAILURE_SCHEMA,
      manifest: buildPrismaManifest([
        ...modelAllocation.mappings,
        ...relationAllocation.mappings,
        ...fieldAllocation.mappings,
      ]),
    };
  }

  let output =
    `// Prisma schema generated from ERD\ngenerator client {\n  provider = "prisma-client-js"\n}\n\ndatasource db {\n  provider = "postgresql"\n  url      = env("DATABASE_URL")\n}\n\n`;

  for (const node of [...nodes].sort(compareNodes)) {
    const modelName = modelAllocation.names.get(`model:${node.id}`);
    if (!modelName) {
      continue;
    }
    output += `model ${modelName} {\n`;

    for (const col of node.data.columns) {
      const fieldName = fieldAllocation.names.get(
        `field:${node.id}:${col.column_name}`,
      );
      if (!fieldName) {
        continue;
      }
      const prismaType = mapToPrismaType(col.data_type);

      let attributes = "";
      const isColUnique = col.column_name === "email";
      if (col.is_pk) {
        attributes += " @id";
        if (
          prismaType === "Int" &&
          col.data_type.toLowerCase().includes("serial")
        ) {
          attributes += " @default(autoincrement())";
        } else if (
          prismaType === "String" &&
          col.data_type.toLowerCase().includes("uuid")
        ) {
          attributes += " @default(uuid())";
        }
      } else if (isColUnique) {
        attributes += " @unique";
      }
      attributes += mapAttribute(col.column_name, fieldName);

      const optional = col.is_not_null ? "" : "?";
      output += `  ${fieldName} ${prismaType}${optional}${attributes}\n`;
    }

    for (const item of resolvedEdges) {
      if (item.sourceNode.id !== node.id) {
        continue;
      }
      const targetModel = modelAllocation.names.get(
        `model:${item.targetNode.id}`,
      );
      const relationName = relationAllocation.names.get(
        `relation:${item.edge.id}`,
      );
      const forwardField = fieldAllocation.names.get(
        `relfield:${item.edge.id}:forward`,
      );
      const sourceField = fieldAllocation.names.get(
        `field:${item.sourceNode.id}:${item.sourceColumns[0]}`,
      );
      const targetField = fieldAllocation.names.get(
        `field:${item.targetNode.id}:${item.targetColumns[0]}`,
      );
      if (
        !targetModel ||
        !relationName ||
        !forwardField ||
        !sourceField ||
        !targetField
      ) {
        continue;
      }
      const sourceColumn = item.sourceNode.data.columns.find(
        (column) => column.column_name === item.sourceColumns[0],
      );
      const optional = sourceColumn?.is_not_null ? "" : "?";
      output += `  ${forwardField} ${targetModel}${optional} @relation("${relationName}", fields: [${sourceField}], references: [${targetField}])\n`;
    }

    for (const item of resolvedEdges) {
      if (item.targetNode.id !== node.id) {
        continue;
      }
      const sourceModel = modelAllocation.names.get(
        `model:${item.sourceNode.id}`,
      );
      const relationName = relationAllocation.names.get(
        `relation:${item.edge.id}`,
      );
      const backField = fieldAllocation.names.get(
        `relfield:${item.edge.id}:back`,
      );
      if (!sourceModel || !relationName || !backField) {
        continue;
      }
      const sourceColumn = item.sourceNode.data.columns.find(
        (column) => column.column_name === item.sourceColumns[0],
      );
      const typeSuffix = sourceColumn?.is_pk ? "?" : "[]";
      output += `  ${backField} ${sourceModel}${typeSuffix} @relation("${relationName}")\n`;
    }

    if (modelName !== node.data.title) {
      output += `  @@map(${quotePrismaString(node.data.title)})\n`;
    }
    output += `}\n\n`;
  }

  return {
    ok: true,
    schema: output.trim() + "\n",
    manifest: buildPrismaManifest([
      ...modelAllocation.mappings,
      ...relationAllocation.mappings,
      ...fieldAllocation.mappings,
    ]),
  };
}

/**
 * Export a Prisma schema string for download. Allocation failure yields a
 * fixed, non-reflecting comment instead of echoing source names.
 */
export function exportPrisma(
  nodes: Node<TableNodeData>[],
  edges: Edge[],
): string {
  return exportPrismaDocument(nodes, edges).schema;
}
