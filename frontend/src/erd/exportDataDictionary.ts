import type { Edge, Node } from '@xyflow/react';

import type { ForeignKeyEdgeData, TableNodeData } from './convert';
import { decodeSourceColumnHandleId, decodeTargetColumnHandleId } from './handleUtils';

const CONTROL_TEXT_RE = /[\u0000-\u001f\u007f]+/g;
const CSV_FORMULA_RE = /^[\s]*[=+\-@\uFF1D\uFF0B\uFF0D\uFF20]/;
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
  const neutralized = CSV_FORMULA_RE.test(text) ? `'${text}` : text;
  return `"${neutralized.replace(/"/g, '""')}"`;
}

function markdownText(value: unknown): string {
  return cellText(value)
    // The regex and lookup table intentionally enumerate the same characters.
    .replace(MARKDOWN_HTML_RE, (char) => MARKDOWN_HTML_ESCAPES[char]!)
    .replace(MARKDOWN_ESCAPE_RE, (char) => `\\${char}`);
}

function columnNamesByNode(nodes: Node<TableNodeData>[]): Map<string, Set<string>> {
  const result = new Map<string, Set<string>>();
  for (const node of nodes) {
    result.set(node.id, new Set((node.data.columns || []).map((column) => column.column_name)));
  }
  return result;
}

type ForeignKeyNodeInfo = {
  columns: Set<string>;
};

export function foreignKeyColumnsByNode(
  nodes: Node<TableNodeData>[],
  edges: Edge[],
): Map<string, ForeignKeyNodeInfo> {
  const map = new Map<string, ForeignKeyNodeInfo>();
  const columnsByNode = columnNamesByNode(nodes);

  for (const edge of edges) {
    const sourceColumns = columnsByNode.get(edge.source);
    const targetColumns = columnsByNode.get(edge.target);
    if (!sourceColumns || !targetColumns) continue;

    const resolvedSourceColumns: string[] = [];
    if (edge.sourceHandle || edge.targetHandle) {
      if (!edge.sourceHandle || !edge.targetHandle) continue;
      const sourceColumn = decodeSourceColumnHandleId(edge.sourceHandle);
      const targetColumn = decodeTargetColumnHandleId(edge.targetHandle);
      if (
        sourceColumn === null ||
        targetColumn === null ||
        !sourceColumns.has(sourceColumn) ||
        !targetColumns.has(targetColumn)
      ) {
        continue;
      }
      resolvedSourceColumns.push(sourceColumn);
    } else {
      const data = edge.data as ForeignKeyEdgeData | undefined;
      const dataSourceColumns = data?.sourceColumns?.filter(Boolean) || [];
      const dataTargetColumns = data?.targetColumns?.filter(Boolean) || [];
      if (
        dataSourceColumns.length === 0 ||
        dataSourceColumns.length !== dataTargetColumns.length ||
        !dataSourceColumns.every((column) => sourceColumns.has(column)) ||
        !dataTargetColumns.every((column) => targetColumns.has(column))
      ) {
        continue;
      }
      resolvedSourceColumns.push(...dataSourceColumns);
    }

    let info = map.get(edge.source);
    if (!info) {
      info = { columns: new Set<string>() };
      map.set(edge.source, info);
    }
    for (const column of resolvedSourceColumns) info.columns.add(column);
  }

  return map;
}

function isForeignKeyColumn(
  edgeColumnsByNode: Map<string, ForeignKeyNodeInfo>,
  node: Node<TableNodeData>,
  columnName: string,
): boolean {
  const info = edgeColumnsByNode.get(node.id);
  if (!info) return false;

  return info.columns.has(columnName);
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
  const fkColumnsByNode = foreignKeyColumnsByNode(nodes, edges);

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
        isForeignKeyColumn(fkColumnsByNode, node, column.column_name) ? 'Y' : 'N',
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
  const fkColumnsByNode = foreignKeyColumnsByNode(nodes, edges);

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
      const fk = isForeignKeyColumn(fkColumnsByNode, node, column.column_name) ? 'Y' : 'N';
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
