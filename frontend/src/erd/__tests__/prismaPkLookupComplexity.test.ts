import { describe, expect, it } from 'vitest';
import type { Edge, Node } from '@xyflow/react';

import type { TableNodeData } from '../convert';
import { exportPrisma } from '../prisma';

describe('exportPrisma primary-key lookup', () => {
  it('does not rescan the source column array for every relation edge', () => {
    const sourceColumns = [
      { column_name: 'user_id', data_type: 'integer', is_pk: true, is_not_null: true },
    ];

    Object.defineProperty(sourceColumns, 'find', {
      configurable: true,
      value: () => {
        throw new Error('source-column find must not run inside the edge pass');
      },
    });

    const users: Node<TableNodeData> = {
      id: 'users',
      position: { x: 0, y: 0 },
      data: {
        title: 'users',
        badges: { pk: true, fk: false },
        columns: [
          { column_name: 'id', data_type: 'serial', is_pk: true, is_not_null: true },
        ],
      },
    };
    const profile: Node<TableNodeData> = {
      id: 'profile',
      position: { x: 100, y: 0 },
      data: {
        title: 'profiles',
        badges: { pk: true, fk: true },
        columns: sourceColumns,
      },
    };
    const edges: Edge[] = [
      {
        id: 'profile-user',
        source: profile.id,
        target: users.id,
        sourceHandle: 'src-user_id',
        targetHandle: 'tgt-id',
        label: 'profiles_user',
      },
    ];

    const output = exportPrisma([users, profile], edges);

    expect(output).toContain('user_id Int @id');
    expect(output).toContain('profiles_user_id profiles? @relation("profiles_user")');
  });
});
