import type { Node, Edge } from '@xyflow/react';
import { normalizeBusinessGroupColor } from './businessGroups';
import type { IndexRecommendation } from './cardinality';
import type { ForeignKeyEdgeData, TableNodeData } from './convert';
import { parseColumnNameFromHandle } from './handleUtils';

export * from './exportDataDictionary';

type SnapshotJson = {
  relations?: Array<{ relation_oid: number; schema_name: string; relation_name: string; relation_kind: string; relation_comment?: string | null }>
  columns?: Array<{ relation_oid: number; column_name: string; data_type: string; is_not_null: boolean; example_value?: string | number | boolean | null }>
  indexes?: Array<{
    relation_oid: number
    index_oid?: number
    index_name: string
    is_unique: boolean
    is_primary: boolean
    method?: string
    columns?: Array<{ name: string; order?: string | null; nulls?: string | null }>
    included_columns?: Array<{ name: string }>
    expression?: string | null
    predicate?: string | null
    definition?: string | null
  }>
  foreign_keys?: Array<{
    source_relation_oid: number
    target_relation_oid: number
    constraint_name?: string | null
    source_columns?: Array<{ name: string }>
    target_columns?: Array<{ name: string }>
    on_update?: string | null
    on_delete?: string | null
  }>
}

export function downloadText(filename: string, text: string) {
  const blob = new Blob([text], { type: 'text/plain;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export function exportSnapshotJson(params: { nodes: Array<Node<TableNodeData>>; edges: Array<Edge<ForeignKeyEdgeData>> }): string {
  const snapshot: SnapshotJson = {
    relations: params.nodes.map((n, idx) => ({
      relation_oid: idx + 1,
      schema_name: n.data.schemaName,
      relation_name: n.data.tableName,
      relation_kind: n.data.relationKind,
    })),
    columns: params.nodes.flatMap((n, idx) => n.data.columns.map((c) => ({
      relation_oid: idx + 1,
      column_name: c.name,
      data_type: c.dataType,
      is_not_null: c.isNotNull,
    }))),
    indexes: params.nodes.flatMap((n, idx) => n.data.indexes.map((i) => ({
      relation_oid: idx + 1,
      index_name: i.name,
      is_unique: i.isUnique,
      is_primary: i.isPrimary,
      columns: i.columns.map((name) => ({ name })),
    }))),
    foreign_keys: params.edges.map((e) => ({
      source_relation_oid: params.nodes.findIndex((n) => n.id === e.source) + 1,
      target_relation_oid: params.nodes.findIndex((n) => n.id === e.target) + 1,
      constraint_name: e.data?.constraintName,
      source_columns: e.data?.sourceColumns.map((name) => ({ name })) ?? [],
      target_columns: e.data?.targetColumns.map((name) => ({ name })) ?? [],
      on_update: e.data?.onUpdate,
      on_delete: e.data?.onDelete,
    })),
  };
  return JSON.stringify(snapshot, null, 2);
}

export function fkColumnsForEdge(edge: Edge<ForeignKeyEdgeData>): { sourceColumn?: string; targetColumn?: string } {
  return {
    sourceColumn: parseColumnNameFromHandle(edge.sourceHandle),
    targetColumn: parseColumnNameFromHandle(edge.targetHandle),
  };
}

export function exportDiagramSvg(params: { nodes: Array<Node<TableNodeData>>; edges: Array<Edge<ForeignKeyEdgeData>> }): string {
  const width = Math.max(1, ...params.nodes.map((n) => (n.position?.x ?? 0) + (n.measured?.width ?? 280) + 40));
  const height = Math.max(1, ...params.nodes.map((n) => (n.position?.y ?? 0) + (n.measured?.height ?? 200) + 40));
  const nodeById = new Map(params.nodes.map((node) => [node.id, node]));
  const relationIndexById = new Map(params.nodes.map((node, index) => [node.id, index + 1]));
  const escapeXml = (value: string) => value
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&apos;');

  const paths = params.edges.map((edge) => {
    const source = nodeById.get(edge.source);
    const target = nodeById.get(edge.target);
    if (!source || !target) return '';
    const x1 = (source.position?.x ?? 0) + (source.measured?.width ?? 280) / 2;
    const y1 = (source.position?.y ?? 0) + (source.measured?.height ?? 200) / 2;
    const x2 = (target.position?.x ?? 0) + (target.measured?.width ?? 280) / 2;
    const y2 = (target.position?.y ?? 0) + (target.measured?.height ?? 200) / 2;
    return `<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke="#64748b" stroke-width="1.5" />`;
  }).join('\n');

  const tables = params.nodes.map((node) => {
    const x = node.position?.x ?? 0;
    const y = node.position?.y ?? 0;
    const nodeWidth = node.measured?.width ?? 280;
    const nodeHeight = node.measured?.height ?? 200;
    const color = normalizeBusinessGroupColor(node.data.businessGroupColor);
    const title = escapeXml(`${node.data.schemaName}.${node.data.tableName}`);
    const relationNumber = relationIndexById.get(node.id) ?? 0;
    return [
      `<g data-relation-index="${relationNumber}">`,
      `<rect x="${x}" y="${y}" width="${nodeWidth}" height="${nodeHeight}" rx="8" fill="#ffffff" stroke="${color}" stroke-width="2" />`,
      `<rect x="${x}" y="${y}" width="${nodeWidth}" height="36" rx="8" fill="${color}" opacity="0.12" />`,
      `<text x="${x + 12}" y="${y + 24}" font-family="system-ui, sans-serif" font-size="14" font-weight="600" fill="#0f172a">${title}</text>`,
      '</g>',
    ].join('\n');
  }).join('\n');

  return [
    `<?xml version="1.0" encoding="UTF-8"?>`,
    `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}">`,
    '<rect width="100%" height="100%" fill="#f8fafc" />',
    paths,
    tables,
    '</svg>',
  ].join('\n');
}

export function exportIndexRecommendationsJson(recommendations: IndexRecommendation[]): string {
  return JSON.stringify(recommendations, null, 2);
}
