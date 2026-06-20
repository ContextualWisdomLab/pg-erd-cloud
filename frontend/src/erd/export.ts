import type { Node, Edge } from '@xyflow/react';
import type { TableNodeData } from './convert';

type SnapshotJson = {
  relations?: Array<{ relation_oid: number; schema_name: string; relation_name: string; relation_kind: string; relation_comment?: string | null }>
  columns?: Array<{ relation_oid: number; column_name: string; data_type: string; is_not_null: boolean; example_value?: string | number | boolean | null }>
  indexes?: Array<{
    relation_oid?: number
    table_oid?: number
    index_name: string
    access_method?: string
    access_method_extension?: string | null
    operator_class_extensions?: string[]
    is_unique?: boolean
    is_primary?: boolean
    index_def?: string
  }>
  fk_edges?: Array<{
    fk_constraint_oid: number
    fk_constraint_name: string
    child_relation_oid: number
    parent_relation_oid: number
    child_column_name: string
    parent_column_name: string
    column_ordinal: number
  }>
}

export function exportDDL(nodes: Node<TableNodeData>[], edges: Edge[]): string {
  let ddl = '-- Generated DDL\n\n';

  // Bolt: Use map for O(1) node lookup instead of O(N) array find
  const nodesById = new Map(nodes.map(n => [n.id, n]));

  // Export tables
  for (const node of nodes) {
    const tableTitle = node.data.title || node.id;
    ddl += `CREATE TABLE "${tableTitle}" (\n`;

    const cols = node.data.columns || [];
    const colLines = cols.map((c) => {
      let line = `  "${c.column_name}" ${c.data_type}`;
      if (c.is_not_null) {
        line += ' NOT NULL';
      }
      return line;
    });

    // Handle primary keys
    const pkCols = cols.filter(c => c.is_pk).map(c => `"${c.column_name}"`);
    if (pkCols.length > 0) {
      colLines.push(`  PRIMARY KEY (${pkCols.join(', ')})`);
    }

    ddl += colLines.join(',\n');
    ddl += '\n);\n\n';
  }

  // Export foreign keys
  for (const edge of edges) {
    const sourceNode = nodesById.get(edge.source);
    const targetNode = nodesById.get(edge.target);

    if (sourceNode && targetNode) {
      const constraintName = edge.label ? edge.label : `fk_${edge.source}_${edge.target}`;
      ddl += `ALTER TABLE "${sourceNode.data.title || sourceNode.id}"\n`;
      ddl += `  ADD CONSTRAINT "${constraintName}"\n`;
      // For simplicity in UI without detailed column mapping we just put placeholder comments
      ddl += `  FOREIGN KEY (/* source columns */)\n`;
      ddl += `  REFERENCES "${targetNode.data.title || targetNode.id}" (/* target columns */);\n\n`;
    }
  }

  return ddl;
}

function escapeXml(value: unknown): string {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&apos;');
}

function plantAlias(id: string): string {
  return `T_${id.replace(/[^A-Za-z0-9_]/g, '_')}`;
}

function plantText(value: unknown): string {
  return String(value ?? '').replaceAll('\\', '\\\\').replaceAll('"', '\\"').replaceAll('\n', ' ');
}

function indexesByRelation(snapshot?: SnapshotJson | null): Map<string, SnapshotJson['indexes']> {
  const map = new Map<string, SnapshotJson['indexes']>();
  for (const ix of snapshot?.indexes || []) {
    const oid = ix.relation_oid ?? ix.table_oid;
    if (typeof oid !== 'number') continue;
    const key = String(oid);
    map.set(key, [...(map.get(key) || []), ix]);
  }
  return map;
}

function indexLabel(ix: NonNullable<SnapshotJson['indexes']>[number]): string {
  const extensions = new Set(
    [ix.access_method_extension, ...(ix.operator_class_extensions || [])].filter(Boolean),
  );
  const method = ix.access_method
    ? ` [${ix.access_method}${extensions.size ? `:${[...extensions].join(',')}` : ''}]`
    : '';
  return `${ix.index_name}${method}${ix.is_unique ? ' unique' : ''}${ix.is_primary ? ' primary' : ''}`;
}

function columnLabel(col: TableNodeData['columns'][number]): string {
  const comment = col.column_comment ? ` (${col.column_comment})` : '';
  const example = col.example_value === null || col.example_value === undefined
    ? ''
    : ` [e.g. ${String(col.example_value)}]`;
  return `${col.column_name}${comment}${example}`;
}

function tableLabel(node: Node<TableNodeData>): string {
  const title = node.data.title || node.id;
  return `${title}${node.data.comment ? ` (${node.data.comment})` : ''}`;
}

export function exportPlantUml(
  nodes: Node<TableNodeData>[],
  edges: Edge[],
  snapshot?: SnapshotJson | null,
): string {
  const indexes = indexesByRelation(snapshot);
  const lines = ['@startuml', 'hide circle', 'skinparam linetype ortho', ''];

  for (const node of nodes) {
    lines.push(`entity "${plantText(tableLabel(node))}" as ${plantAlias(node.id)} {`);
    for (const col of node.data.columns || []) {
      lines.push(`  ${col.is_pk ? '*' : ''}${plantText(columnLabel(col))} : ${plantText(col.data_type)}${col.is_not_null ? ' <<not null>>' : ''}`);
    }
    for (const ix of indexes.get(node.id) || []) {
      lines.push(`  <<index>> ${plantText(indexLabel(ix))}`);
    }
    lines.push('}', '');
  }

  for (const edge of edges) {
    const label = edge.label ? ` : ${plantText(edge.label)}` : '';
    lines.push(`${plantAlias(edge.source)} --> ${plantAlias(edge.target)}${label}`);
  }

  lines.push('@enduml', '');
  return lines.join('\n');
}

export function exportDiagramSvg(
  nodes: Node<TableNodeData>[],
  edges: Edge[],
  snapshot?: SnapshotJson | null,
): string {
  // Bolt: Use map for O(1) node lookup instead of O(N) array find
  const nodesById = new Map(nodes.map(n => [n.id, n]));
  const width = 280;
  const headerHeight = 34;
  const rowHeight = 22;
  const padding = 40;
  const indexes = indexesByRelation(snapshot);
  const heights = new Map(
    nodes.map((node) => {
      // ponytail: cap rendered index rows; add full index export when the canvas carries index nodes.
      const indexRows = Math.min(indexes.get(node.id)?.length || 0, 8);
      return [node.id, headerHeight + rowHeight * ((node.data.columns?.length || 0) + indexRows + (indexRows ? 1 : 0))];
    }),
  );
  const minX = Math.min(...nodes.map((n) => n.position.x), 0);
  const minY = Math.min(...nodes.map((n) => n.position.y), 0);
  const maxX = Math.max(...nodes.map((n) => n.position.x + width), width);
  const maxY = Math.max(...nodes.map((n) => n.position.y + (heights.get(n.id) || headerHeight)), headerHeight);
  const offsetX = padding - minX;
  const offsetY = padding - minY;
  const svgWidth = maxX - minX + padding * 2;
  const svgHeight = maxY - minY + padding * 2;
  const parts = [
    `<svg xmlns="http://www.w3.org/2000/svg" width="${svgWidth}" height="${svgHeight}" viewBox="0 0 ${svgWidth} ${svgHeight}">`,
    '<defs><marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#64748b"/></marker></defs>',
    '<rect width="100%" height="100%" fill="#f8fafc"/>',
  ];

  for (const edge of edges) {
    const source = nodesById.get(edge.source);
    const target = nodesById.get(edge.target);
    if (!source || !target) continue;
    const sx = source.position.x + offsetX + width;
    const sy = source.position.y + offsetY + (heights.get(source.id) || headerHeight) / 2;
    const tx = target.position.x + offsetX;
    const ty = target.position.y + offsetY + (heights.get(target.id) || headerHeight) / 2;
    const mx = (sx + tx) / 2;
    parts.push(`<path d="M ${sx} ${sy} C ${mx} ${sy}, ${mx} ${ty}, ${tx} ${ty}" fill="none" stroke="#64748b" stroke-width="1.5" marker-end="url(#arrow)"/>`);
    if (edge.label) {
      parts.push(`<text x="${mx}" y="${(sy + ty) / 2 - 4}" font-family="system-ui, sans-serif" font-size="11" fill="#475569">${escapeXml(edge.label)}</text>`);
    }
  }

  for (const node of nodes) {
    const x = node.position.x + offsetX;
    const y = node.position.y + offsetY;
    const height = heights.get(node.id) || headerHeight;
    parts.push(`<rect x="${x}" y="${y}" width="${width}" height="${height}" rx="8" fill="#fff" stroke="#cbd5e1"/>`);
    parts.push(`<rect x="${x}" y="${y}" width="${width}" height="${headerHeight}" rx="8" fill="#e0f2fe" stroke="#cbd5e1"/>`);
    parts.push(`<text x="${x + 12}" y="${y + 22}" font-family="system-ui, sans-serif" font-size="13" font-weight="700" fill="#0f172a">${escapeXml(tableLabel(node))}</text>`);
    let rowY = y + headerHeight + 16;
    for (const col of node.data.columns || []) {
      parts.push(`<text x="${x + 12}" y="${rowY}" font-family="ui-monospace, monospace" font-size="11" fill="#111827">${col.is_pk ? '* ' : ''}${escapeXml(columnLabel(col))}: ${escapeXml(col.data_type)}${col.is_not_null ? ' not null' : ''}</text>`);
      rowY += rowHeight;
    }
    const tableIndexes = indexes.get(node.id) || [];
    if (tableIndexes.length > 0) {
      parts.push(`<text x="${x + 12}" y="${rowY}" font-family="system-ui, sans-serif" font-size="11" font-weight="700" fill="#475569">Indexes</text>`);
      rowY += rowHeight;
    }
    for (const ix of tableIndexes.slice(0, 8)) {
      parts.push(`<text x="${x + 12}" y="${rowY}" font-family="ui-monospace, monospace" font-size="11" fill="#334155">${escapeXml(indexLabel(ix))}</text>`);
      rowY += rowHeight;
    }
  }

  parts.push('</svg>');
  return parts.join('\n');
}

export function downloadText(filename: string, contents: string, type = 'text/plain'): void {
  const blob = new Blob([contents], { type });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}
