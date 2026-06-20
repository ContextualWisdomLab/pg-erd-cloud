import type { Edge, Node } from '@xyflow/react';

import { exportDiagramSvg, exportPlantUml } from './export';
import type { TableNodeData } from './convert';

const nodes: Array<Node<TableNodeData>> = [
  {
    id: '1',
    type: 'tableNode',
    position: { x: 0, y: 0 },
    data: {
      title: 'public.users',
      comment: 'application users',
      columns: [{ column_name: 'id', data_type: 'integer', is_not_null: true, is_pk: true, column_comment: 'user id', example_value: '1001' }],
      badges: { pk: true, fk: false },
    },
  },
  {
    id: '2',
    type: 'tableNode',
    position: { x: 360, y: 0 },
    data: {
      title: 'public.orders',
      columns: [{ column_name: 'user_id', data_type: 'integer', is_not_null: true, is_pk: false }],
      badges: { pk: false, fk: true },
    },
  },
];

const edges: Edge[] = [{ id: 'fk', source: '2', target: '1', label: 'fk_orders_user', type: 'smoothstep' }];
const snapshot = {
  indexes: [
    {
      table_oid: 2,
      index_name: 'idx_orders_user_id',
      access_method: 'gin',
      operator_class_extensions: ['btree_gin'],
      is_unique: false,
    },
  ],
};

const uml = exportPlantUml(nodes, edges, snapshot);
const svg = exportDiagramSvg(nodes, edges, snapshot);

for (const expected of ['public.users', 'application users', 'fk_orders_user', 'idx_orders_user_id', 'gin:btree_gin', 'user id', '1001']) {
  if (!uml.includes(expected) || !svg.includes(expected)) {
    throw new Error(`export self-check missing ${expected}`);
  }
}
