import type { Edge, Node } from '@xyflow/react';
import { describe, expect, it } from 'vitest';

import type { TableNodeData } from '../convert';
import { exportDDL } from '../export';
import {
  parseColumnNameFromHandle,
  sourceColumnHandleId,
  targetColumnHandleId,
} from '../handleUtils';

function tableNode(
  id: string,
  title: string,
  columns: TableNodeData['columns'],
): Node<TableNodeData> {
  const hasPrimaryKey = columns.reduce(
    (hasPrimary, column) => hasPrimary || column.is_pk,
    false,
  );
  return {
    id,
    type: 'tableNode',
    position: { x: 0, y: 0 },
    data: {
      title,
      columns,
      badges: { pk: hasPrimaryKey, fk: false },
    },
  };
}

describe('foreign-key handle lookup regressions', () => {
  it('rejects partially parsed hexadecimal handle tokens', () => {
    expect(parseColumnNameFromHandle('src-c-0069junk-0064')).toBeNull();
  });

  it('resolves edge handles without calling Array.some for every edge', () => {
    const sourceColumns: TableNodeData['columns'] = [
      {
        column_name: 'user_id',
        data_type: 'integer',
        is_not_null: true,
        is_pk: false,
      },
    ];
    const targetColumns: TableNodeData['columns'] = [
      {
        column_name: 'id',
        data_type: 'integer',
        is_not_null: true,
        is_pk: true,
      },
    ];
    Object.defineProperty(sourceColumns, 'some', {
      value: () => {
        throw new Error('per-edge source column scan');
      },
    });
    Object.defineProperty(targetColumns, 'some', {
      value: () => {
        throw new Error('per-edge target column scan');
      },
    });

    const sourceNode = tableNode('posts', 'public.posts', sourceColumns);
    const targetNode = tableNode('users', 'public.users', targetColumns);
    const edge: Edge = {
      id: 'fk_posts_users',
      source: sourceNode.id,
      target: targetNode.id,
      sourceHandle: sourceColumnHandleId('user_id'),
      targetHandle: targetColumnHandleId('id'),
    };

    const ddl = exportDDL([sourceNode, targetNode], [edge]);

    expect(ddl).toContain('FOREIGN KEY ("user_id")');
    expect(ddl).toContain('REFERENCES "public.users" ("id")');
  });

  it('preserves the explicitly supported empty-column handle encoding', () => {
    const sourceNode = tableNode('source', 'public.source', [
      {
        column_name: '',
        data_type: 'integer',
        is_not_null: true,
        is_pk: true,
      },
    ]);
    const targetNode = tableNode('target', 'public.target', [
      {
        column_name: 'id',
        data_type: 'integer',
        is_not_null: true,
        is_pk: true,
      },
    ]);
    const edge: Edge = {
      id: 'fk_empty_handle',
      source: sourceNode.id,
      target: targetNode.id,
      sourceHandle: 'src-c-empty',
      targetHandle: targetColumnHandleId('id'),
    };

    const ddl = exportDDL([sourceNode, targetNode], [edge]);

    expect(ddl).toContain('FOREIGN KEY ("unnamed")');
    expect(ddl).toContain('REFERENCES "public.target" ("id")');
    expect(ddl).not.toContain('/* source columns */');
  });
});
