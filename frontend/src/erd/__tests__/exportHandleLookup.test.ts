import { describe, expect, it } from 'vitest';
import type { Edge, Node } from '@xyflow/react';

import type { TableNodeData } from '../convert';
import { exportDDL } from '../export';
import { sourceColumnHandleId, targetColumnHandleId } from '../handleUtils';

function tableNode(
  id: string,
  title: string,
  columns: TableNodeData['columns'],
): Node<TableNodeData> {
  return {
    id,
    type: 'tableNode',
    position: { x: 0, y: 0 },
    data: {
      title,
      columns,
      badges: { pk: columns.some((column) => column.is_pk), fk: false },
    },
  };
}

describe('exportDDL foreign-key handle lookup', () => {
  it('selects the exact handled columns instead of the multi-column fallback', () => {
    const child = tableNode('child', 'public.child', [
      { column_name: 'id', data_type: 'integer', is_not_null: true, is_pk: true },
      { column_name: 'legacy_parent_id', data_type: 'integer', is_not_null: true, is_pk: false },
      { column_name: 'chosen_parent_id', data_type: 'integer', is_not_null: true, is_pk: false },
    ]);
    const parent = tableNode('parent', 'public.parent', [
      { column_name: 'legacy_id', data_type: 'integer', is_not_null: true, is_pk: true },
      { column_name: 'chosen_id', data_type: 'integer', is_not_null: true, is_pk: true },
    ]);
    const edge: Edge = {
      id: 'fk_chosen',
      source: child.id,
      target: parent.id,
      sourceHandle: sourceColumnHandleId('chosen_parent_id'),
      targetHandle: targetColumnHandleId('chosen_id'),
      label: 'fk_chosen',
    };

    const ddl = exportDDL([child, parent], [edge]);

    expect(ddl).toContain('FOREIGN KEY ("chosen_parent_id")');
    expect(ddl).toContain('REFERENCES "public.parent" ("chosen_id")');
    expect(ddl).not.toContain('FOREIGN KEY ("legacy_parent_id", "chosen_parent_id")');
    expect(ddl).not.toContain('REFERENCES "public.parent" ("legacy_id", "chosen_id")');
  });

  it('ignores malformed null column names while building the handle map', () => {
    const child = tableNode('child', 'public.child', [
      { column_name: null, data_type: 'integer', is_not_null: false, is_pk: false } as unknown as TableNodeData['columns'][number],
    ]);
    const parent = tableNode('parent', 'public.parent', [
      { column_name: 'id', data_type: 'integer', is_not_null: true, is_pk: true },
    ]);
    const edge: Edge = {
      id: 'fk_malformed',
      source: child.id,
      target: parent.id,
      sourceHandle: sourceColumnHandleId('missing'),
      targetHandle: targetColumnHandleId('id'),
      label: 'fk_malformed',
    };

    expect(() => exportDDL([child, parent], [edge])).not.toThrow();
    const ddl = exportDDL([child, parent], [edge]);
    expect(ddl).toContain('FOREIGN KEY (/* source columns */)');
    expect(ddl).toContain('REFERENCES "public.parent" (/* target columns */)');
  });
});
