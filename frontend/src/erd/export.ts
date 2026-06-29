import type { Node, Edge } from '@xyflow/react';
import { normalizeBusinessGroupColor } from './businessGroups';
import type { IndexRecommendation } from './cardinality';
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

type SnapshotIndex = NonNullable<SnapshotJson['indexes']>[number];

type DisplayIndex = SnapshotIndex | IndexRecommendation;

const SQL_IDENTIFIER_QUOTE_RE = /"/g;
const SQL_ACCESS_METHOD_RE = /^[A-Za-z_][A-Za-z0-9_]*$/;
const SQL_DATA_TYPE_RE = /^[A-Za-z0-9_ .,[\]()]+$/;
const PLANT_TEXT_ESCAPE_RE = /[\\\r\n]/g;

function quoteSqlIdentifier(value: unknown): string {
  const text = String(value ?? '').trim() || 'unnamed';
  return `"${text.replace(SQL_IDENTIFIER_QUOTE_RE, '""')}"`;
}

function sqlAccessMethod(value: unknown): string {
  const text = String(value ?? '').trim();
  return SQL_ACCESS_METHOD_RE.test(text) ? text : 'btree';
}

function sqlDataType(value: unknown): string {
  const text = String(value ?? '').trim();
  return SQL_DATA_TYPE_RE.test(text) ? text : 'text';
}

export function exportDDL(nodes: Node<TableNodeData>[], edges: Edge[]): string {
  let ddl = '-- Generated DDL\n\n';

  // Bolt: Use map for O(1) node lookup instead of O(N) array find
  const nodesById = new Map(nodes.map(n => [n.id, n]));

  // Export tables
  for (const node of nodes) {
    const tableTitle = node.data.title || node.id;
    ddl += `CREATE TABLE ${quoteSqlIdentifier(tableTitle)} (\n`;

    const cols = node.data.columns || [];
    const colLines = cols.map((c) => {
      const columnName = quoteSqlIdentifier(c.column_name);
      let line = `  ${columnName} ${sqlDataType(c.data_type)}`;
      if (c.is_not_null) {
        line += ' NOT NULL';
      }
      return line;
    });

    // Handle primary keys
    const pkCols = cols
      .filter(c => c.is_pk)
      .map(c => quoteSqlIdentifier(c.column_name));
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
      const sourceTable = quoteSqlIdentifier(sourceNode.data.title || sourceNode.id);
      const targetTable = quoteSqlIdentifier(targetNode.data.title || targetNode.id);
      ddl += `ALTER TABLE ${sourceTable}\n`;
      ddl += `  ADD CONSTRAINT ${quoteSqlIdentifier(constraintName)}\n`;
      // For simplicity in UI without detailed column mapping we just put placeholder comments
      ddl += `  FOREIGN KEY (/* source columns */)\n`;
      ddl += `  REFERENCES ${targetTable} (/* target columns */);\n\n`;
    }
  }

  const emittedIndexes = new Set<string>();
  const indexLines: string[] = [];
  for (const node of nodes) {
    const tableTitle = node.data.title || node.id;
    for (const index of node.data.indexes || []) {
      if (emittedIndexes.has(index.index_name) || index.columns.length === 0) {
        continue;
      }
      emittedIndexes.add(index.index_name);
      const cols = index.columns
        .map((column) => quoteSqlIdentifier(column))
        .join(', ');
      const indexName = quoteSqlIdentifier(index.index_name);
      const quotedTable = quoteSqlIdentifier(tableTitle);
      const accessMethod = sqlAccessMethod(index.access_method);
      indexLines.push(
        `CREATE INDEX CONCURRENTLY ${indexName} ON ${quotedTable} USING ${accessMethod} (${cols});`,
      );
    }
  }
  if (indexLines.length > 0) {
    ddl += '-- Indexes\n';
    ddl += indexLines.join('\n');
    ddl += '\n\n';
  }

  return ddl;
}

const XML_ESCAPE_RE = /[&<>"']/g;
const XML_ESCAPES: Record<string, string> = {
  '&': '&amp;',
  '<': '&lt;',
  '>': '&gt;',
  '"': '&quot;',
  "'": '&#39;',
};

function escapeXml(value: unknown): string {
  return String(value ?? '').replace(
    XML_ESCAPE_RE,
    (char) => XML_ESCAPES[char] ?? char,
  );
}

function plantAlias(id: string): string {
  return `T_${id.replace(/[^A-Za-z0-9_]/g, '_')}`;
}

function plantText(value: unknown): string {
  return escapeXml(value).replace(
    PLANT_TEXT_ESCAPE_RE,
    (char) => (char === '\\' ? '\\\\' : ' '),
  );
}

function indexesByRelation(snapshot?: SnapshotJson | null): Map<string, SnapshotJson['indexes']> {
  const map = new Map<string, SnapshotJson['indexes']>();
  for (const ix of snapshot?.indexes || []) {
    const oid = ix.relation_oid ?? ix.table_oid;
    if (typeof oid !== 'number') continue;
    const key = String(oid);
    // ⚡ Bolt: Optimize array spread to O(1) amortized push, avoiding O(N^2) complexity and excessive GC when grouping indexes by relation.
    const list = map.get(key);
    if (list) {
      list.push(ix);
    } else {
      map.set(key, [ix]);
    }
  }
  return map;
}

function indexLabel(ix: DisplayIndex): string {
  const extensions = 'operator_class_extensions' in ix
    ? new Set(
        [ix.access_method_extension, ...(ix.operator_class_extensions || [])].filter(Boolean),
      )
    : new Set<string>();
  const method = ix.access_method
    ? ` [${ix.access_method}${extensions.size ? `:${[...extensions].join(',')}` : ''}]`
    : '';
  const columns = 'columns' in ix ? ` (${ix.columns.join(', ')})` : '';
  const unique = 'is_unique' in ix && ix.is_unique ? ' unique' : '';
  const primary = 'is_primary' in ix && ix.is_primary ? ' primary' : '';
  return `${ix.index_name}${method}${columns}${unique}${primary}`;
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
  const comment = node.data.comment ? ` (${node.data.comment})` : '';
  const group = node.data.businessGroup ? ` [${node.data.businessGroup.name}]` : '';
  return `${title}${group}${comment}`;
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
    for (const ix of [...(indexes.get(node.id) || []), ...(node.data.indexes || [])]) {
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
      const indexRows = Math.min((indexes.get(node.id)?.length || 0) + (node.data.indexes?.length || 0), 8);
      return [node.id, headerHeight + rowHeight * ((node.data.columns?.length || 0) + indexRows + (indexRows ? 1 : 0))];
    }),
  );
  // ⚡ Bolt: Use a standard O(N) loop instead of spread syntax and map() to calculate bounds.
  // This prevents 'Maximum call stack size exceeded' on large graphs and avoids garbage allocations.
  let minX = 0;
  let minY = 0;
  let maxX = width;
  let maxY = headerHeight;
  for (const n of nodes) {
    minX = Math.min(minX, n.position.x);
    minY = Math.min(minY, n.position.y);
    maxX = Math.max(maxX, n.position.x + width);
    maxY = Math.max(maxY, n.position.y + (heights.get(n.id) || headerHeight));
  }
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
    const groupColor = node.data.businessGroup
      ? normalizeBusinessGroupColor(node.data.businessGroup.color)
      : '#e0f2fe';
    parts.push(`<rect x="${x}" y="${y}" width="${width}" height="${height}" rx="8" fill="#fff" stroke="#cbd5e1"/>`);
    parts.push(`<rect x="${x}" y="${y}" width="${width}" height="${headerHeight}" rx="8" fill="${escapeXml(groupColor)}" fill-opacity="${node.data.businessGroup ? '0.18' : '1'}" stroke="#cbd5e1"/>`);
    if (node.data.businessGroup) {
      parts.push(`<rect x="${x}" y="${y}" width="6" height="${height}" rx="3" fill="${escapeXml(groupColor)}"/>`);
    }
    parts.push(`<text x="${x + 12}" y="${y + 22}" font-family="system-ui, sans-serif" font-size="13" font-weight="700" fill="#0f172a">${escapeXml(tableLabel(node))}</text>`);
    let rowY = y + headerHeight + 16;
    for (const col of node.data.columns || []) {
      parts.push(`<text x="${x + 12}" y="${rowY}" font-family="ui-monospace, monospace" font-size="11" fill="#111827">${col.is_pk ? '* ' : ''}${escapeXml(columnLabel(col))}: ${escapeXml(col.data_type)}${col.is_not_null ? ' not null' : ''}</text>`);
      rowY += rowHeight;
    }
    const tableIndexes: DisplayIndex[] = [
      ...(indexes.get(node.id) || []),
      ...(node.data.indexes || []),
    ];
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
