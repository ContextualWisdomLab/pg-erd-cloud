import type { Edge, Node } from '@xyflow/react';

import type { ForeignKeyEdgeData, TableNodeData } from './convert';
import { sourceColumnHandleId } from './handleUtils';

const CONTROL_TEXT_RE = /[\u0000-\u001f\u007f]+/g;
const CSV_FORMULA_RE = /^[=+\-@]/;
const MARKDOWN_ESCAPE_RE = /[\\|`\[\]()]/g;
const MARKDOWN_HTML_RE = /[&<>]/g;
const MARKDOWN_HTML_ESCAPES: Record<string, string> = {
  '&': '&amp;',
  '<': '&lt;',
  '>': '&gt;',
};

function cellText(value: unknown): string {
  return String(value ?? '').replace(CONTROL_TEXT_RE, ' ');
}

function csvCell(value: unknown): string {
  const text = cellText(value);
  const neutralized = CSV_FORMULA_RE.test(text.trimStart()) ? `'${text}` : text;
  return `"${neutralized.replace(/"/g, '""')}"`;
}

function markdownText(value: unknown): string {
  return cellText(value)
    .replace(MARKDOWN_HTML_RE, (char) => MARKDOWN_HTML_ESCAPES[char] ?? char)
    .replace(MARKDOWN_ESCAPE_RE, (char) => `\\${char}`);
}

function sourceColumnsForEdge(edge: Edge): Set<string> {
  const columns = new Set<string>();
  const data = edge.data as ForeignKeyEdgeData | undefined;
  for (const column of data?.sourceColumns || []) {
    if (column) columns.add(column);
  }
  return columns;
}

function foreignKeyColumnsByNode(edges: Edge[]): Map<string, Set<string>> {
  const map = new Map<string, Set<string>>();

  for (const edge of edges) {
    let columns = map.get(edge.source);
    if (!columns) {
      columns = new Set<string>();
      map.set(edge.source, columns);
    }

    for (const column of sourceColumnsForEdge(edge)) {
      columns.add(column);
    }
  }

  return map;
}

function isForeignKeyColumn(
  edgeColumnsByNode: Map<string, Set<string>>,
  node: Node<TableNodeData>,
  columnName: string,
  edges: Edge[],
): boolean {
  if (edgeColumnsByNode.get(node.id)?.has(columnName)) {
    return true;
  }

  const handleId = sourceColumnHandleId(columnName);
  return edges.some((edge) => edge.source === node.id && edge.sourceHandle === handleId);
}

function exampleValue(value: TableNodeData['columns'][number]['example_value']): string {
  return value === null || value === undefined ? '' : String(value);
}

export function exportDictionaryCsv(
  nodes: Node<TableNodeData>[],
  edges: Edge[],
): string {
  const header = [
    'Table Name',
    'Table Comment',
    'Column Name',
    'Data Type',
    'PK',
    'FK',
    'Not Null',
    'Column Comment',
    'Example Value',
  ];
  const rows: unknown[][] = [header];
  const fkColumnsByNode = foreignKeyColumnsByNode(edges);

  for (const node of nodes) {
    const tableName = node.data.title || node.id;
    const tableComment = node.data.comment || '';
    const columns = node.data.columns || [];

    if (columns.length === 0) {
      rows.push([tableName, tableComment, '', '', '', '', '', '', '']);
      continue;
    }

    for (const column of columns) {
      rows.push([
        tableName,
        tableComment,
        column.column_name,
        column.data_type,
        column.is_pk ? 'Y' : 'N',
        isForeignKeyColumn(fkColumnsByNode, node, column.column_name, edges) ? 'Y' : 'N',
        column.is_not_null ? 'Y' : 'N',
        column.column_comment || '',
        exampleValue(column.example_value),
      ]);
    }
  }

  return rows.map((row) => row.map(csvCell).join(',')).join('\n');
}

export function exportDictionaryMarkdown(
  nodes: Node<TableNodeData>[],
  edges: Edge[],
): string {
  const lines: string[] = ['# Data Dictionary', ''];
  const fkColumnsByNode = foreignKeyColumnsByNode(edges);

  if (nodes.length === 0) {
    lines.push('No tables found.');
    return lines.join('\n');
  }

  for (const node of nodes) {
    const tableName = markdownText(node.data.title || node.id);
    const tableComment = node.data.comment ? ` (${markdownText(node.data.comment)})` : '';
    const columns = node.data.columns || [];
    lines.push(`## Table: ${tableName}${tableComment}`);

    if (columns.length === 0) {
      lines.push('No columns.', '');
      continue;
    }

    lines.push('| Column Name | Data Type | PK | FK | Not Null | Comment | Example |');
    lines.push('|---|---|---|---|---|---|---|');

    for (const column of columns) {
      const pk = column.is_pk ? 'Y' : 'N';
      const fk = isForeignKeyColumn(fkColumnsByNode, node, column.column_name, edges) ? 'Y' : 'N';
      const notNull = column.is_not_null ? 'Y' : 'N';
      const comment = column.column_comment || '';
      lines.push(
        `| ${markdownText(column.column_name)} | ${markdownText(column.data_type)} | ${pk} | ${fk} | ${notNull} | ${markdownText(comment)} | ${markdownText(exampleValue(column.example_value))} |`,
      );
    }
    lines.push('');
  }

  return lines.join('\n').trim();
}
