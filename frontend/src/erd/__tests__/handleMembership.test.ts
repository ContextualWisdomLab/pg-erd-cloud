import { describe, expect, it } from 'vitest';
import type { Edge, Node } from '@xyflow/react';

import type { TableNodeData } from '../convert';
import { exportDDL } from '../export';
import { sourceColumnHandleId, targetColumnHandleId } from '../handleUtils';

describe('ERD edge handle membership', () => {
  it('does not trust a decodable handle for a column absent from its endpoint node', () => {
    const parent: Node<TableNodeData> = {
      id: 'parent',
      type: 'tableNode',
      position: { x: 0, y: 0 },
      data: {
        title: 'public.users',
        columns: [
          { column_name: 'id', data_type: 'integer', is_not_null: true, is_pk: true },
        ],
        badges: { pk: true, fk: false },
      },
    };
    const child: Node<TableNodeData> = {
      id: 'child',
      type: 'tableNode',
      position: { x: 0, y: 0 },
      data: {
        title: 'public.posts',
        columns: [
          { column_name: 'user_id', data_type: 'integer', is_not_null: true, is_pk: false },
        ],
        badges: { pk: false, fk: true },
      },
    };
    const staleEdge: Edge = {
      id: 'fk-stale',
      source: child.id,
      target: parent.id,
      sourceHandle: sourceColumnHandleId('ghost_user_id'),
      targetHandle: targetColumnHandleId('ghost_id'),
      label: 'fk_posts_users',
    };

    const ddl = exportDDL([parent, child], [staleEdge]);

    expect(ddl).not.toContain('ghost_user_id');
    expect(ddl).not.toContain('ghost_id');
    expect(ddl).toContain('FOREIGN KEY ("user_id")');
    expect(ddl).toContain('REFERENCES "public.users" ("id")');
  });
});
