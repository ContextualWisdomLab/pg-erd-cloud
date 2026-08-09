import type { Edge, Node } from '@xyflow/react';
import { describe, expect, it } from 'vitest';

import type { TableNodeData } from '../convert';
import { exportDDL } from '../export';
import { parseColumnNameFromHandle, sourceColumnHandleId, targetColumnHandleId } from '../handleUtils';

function tableNode(id: string, title: string, columns: TableNodeData['columns']): Node<TableNodeData> {
  return {
    id,
    type: 'tableNode',
    position: { x: 0, y: 0 },
    data: { title, columns, badges: { pk: columns.some((column) => column.is_pk), fk: false } },
  };
}

describe('foreign-key handle lookup regressions', () => {
  it('rejects malformed, oversized, and invalid-code-point handles', () => {
    expect(parseColumnNameFromHandle('src-c-0069junk-0064')).toBeNull();
    expect(parseColumnNameFromHandle(`src-c-${'0069-'.repeat(150)}`)).toBeNull();
    expect(parseColumnNameFromHandle('src-c-110000')).toBeNull();
  });

  it('indexes node columns once rather than rescanning for each edge', () => {
    let reads = 0;
    const sourceColumn = {
      get column_name() { reads += 1; return 'user_id'; },
      data_type: 'integer', is_not_null: true, is_pk: false,
    };
    const targetColumn = {
      get column_name() { reads += 1; return 'id'; },
      data_type: 'integer', is_not_null: true, is_pk: true,
    };
    const sourceNode = tableNode('posts', 'public.posts', [sourceColumn]);
    const targetNode = tableNode('users', 'public.users', [targetColumn]);
    const edges: Edge[] = Array.from({ length: 100 }, (_, index) => ({
      id: `fk_${index}`,
      source: sourceNode.id,
      target: targetNode.id,
      sourceHandle: sourceColumnHandleId('user_id'),
      targetHandle: targetColumnHandleId('id'),
    }));

    const ddl = exportDDL([sourceNode, targetNode], edges);

    expect(ddl).toContain('FOREIGN KEY ("user_id")');
    expect(reads).toBeLessThan(20);
  });

  it('preserves the supported empty-column handle encoding', () => {
    const sourceNode = tableNode('source', 'public.source', [
      { column_name: '', data_type: 'integer', is_not_null: true, is_pk: true },
    ]);
    const targetNode = tableNode('target', 'public.target', [
      { column_name: 'id', data_type: 'integer', is_not_null: true, is_pk: true },
    ]);
    const ddl = exportDDL([sourceNode, targetNode], [{
      id: 'fk_empty_handle', source: sourceNode.id, target: targetNode.id,
      sourceHandle: 'src-c-empty', targetHandle: targetColumnHandleId('id'),
    }]);

    expect(ddl).toContain('FOREIGN KEY ("unnamed")');
    expect(ddl).not.toContain('/* source columns */');
  });
});
