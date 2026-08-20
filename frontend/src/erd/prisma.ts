import type { Edge, Node } from "@xyflow/react";
import type { TableNodeData, ForeignKeyEdgeData } from "./convert";
import { sourceColumnHandleId, targetColumnHandleId } from "./handleUtils";
import {
  allocatePrismaIdentifiers,
  buildPrismaManifest,
  preferredPrismaName,
  type PrismaIdentifierFailure,
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
  failure?: PrismaIdentifierFailure;
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

type TableIdentity = { schemaName?: string; tableName: string };

function tableIdentity(node: Node<TableNodeData>): TableIdentity {
  const schemaName = node.data.schema_name?.trim();
  const relationName = node.data.relation_name?.trim();
  if (relationName) {
    return { schemaName, tableName: relationName };
  }
  if (schemaName) {
    return { schemaName, tableName: node.data.title };
  }
  const separator = node.data.title.indexOf(".");
  if (separator > 0 && separator < node.data.title.length - 1) {
    return {
      schemaName: node.data.title.slice(0, separator),
      tableName: node.data.title.slice(separator + 1),
    };
  }
  return { tableName: node.data.title };
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
    source: tableIdentity(node).tableName,
  }));
  const modelAllocation = allocatePrismaIdentifiers(
    modelRequests,
    options?.maxAttempts,
  );
  if (!modelAllocation.ok) {
    return {
      ok: false,
      schema: PRISMA_EXPORT_FAILURE_SCHEMA,
      manifest: buildPrismaManifest(
        modelAllocation.mappings,
        modelAllocation.failure,
      ),
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
      ], relationAllocation.failure),
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
      ], fieldAllocation.failure),
    };
  }

  const schemas = [...new Set(
    nodes
      .map((node) => tableIdentity(node).schemaName)
      .filter((schema): schema is string => Boolean(schema)),
  )].sort();
  let output =
    `// Prisma schema generated from ERD\ngenerator client {\n  provider = "prisma-client-js"\n${schemas.length > 0 ? '  previewFeatures = ["multiSchema"]\n' : ""}}\n\ndatasource db {\n  provider = "postgresql"\n  url      = env("DATABASE_URL")\n${schemas.length > 0 ? `  schemas   = ${JSON.stringify(schemas)}\n` : ""}}\n\n`;

  for (const node of [...nodes].sort(compareNodes)) {
    const identity = tableIdentity(node);
    const modelName = modelAllocation.names.get(`model:${node.id}`);
    if (!modelName) {
      continue;
    }
    output += `model ${modelName} {\n`;

    const primaryColumns = node.data.columns.filter((col) => col.is_pk);
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
      if (col.is_pk && primaryColumns.length === 1) {
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
      const sourceFields = item.sourceColumns.map((column) =>
        fieldAllocation.names.get(
          `field:${item.sourceNode.id}:${column}`,
        ),
      );
      const targetFields = item.targetColumns.map((column) =>
        fieldAllocation.names.get(
          `field:${item.targetNode.id}:${column}`,
        ),
      );
      if (
        !targetModel ||
        !relationName ||
        !forwardField ||
        sourceFields.some((field) => !field) ||
        targetFields.some((field) => !field)
      ) {
        continue;
      }
      const optional = item.sourceColumns.every((columnName) =>
        item.sourceNode.data.columns.find(
          (column) => column.column_name === columnName,
        )?.is_not_null,
      )
        ? ""
        : "?";
      output += `  ${forwardField} ${targetModel}${optional} @relation("${relationName}", fields: [${sourceFields.join(", ")}], references: [${targetFields.join(", ")}])\n`;
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
      output += `  ${backField} ${sourceModel}[] @relation("${relationName}")\n`;
    }

    if (primaryColumns.length > 1) {
      const primaryFields = primaryColumns.map((column) =>
        fieldAllocation.names.get(`field:${node.id}:${column.column_name}`),
      );
      output += `  @@id([${primaryFields.join(", ")}])\n`;
    }
    output += `  @@map(${quotePrismaString(identity.tableName)})\n`;
    if (identity.schemaName) {
      output += `  @@schema(${quotePrismaString(identity.schemaName)})\n`;
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
