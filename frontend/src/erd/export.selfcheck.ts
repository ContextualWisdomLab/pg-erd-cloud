import type { Edge, Node } from '@xyflow/react';

import { buildIndexRecommendations } from './cardinality';
import { exportDDL, exportDiagramSvg, exportPlantUml } from './export';
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
      indexes: [
        {
          index_name: 'idx_orders_user_id_cardinality',
          columns: ['user_id'],
          access_method: 'btree',
          estimated_distinct: 9000,
          cardinality_ratio: 0.9,
          strength: 'recommended',
          reason: '90% distinct; 선택도가 높습니다.',
          source: 'cardinality-wizard',
        },
      ],
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
const ddl = exportDDL(nodes, edges);

for (const expected of ['public.users', 'application users', 'fk_orders_user', 'idx_orders_user_id', 'gin:btree_gin', 'idx_orders_user_id_cardinality', 'user id', '1001']) {
  if (!uml.includes(expected) || !svg.includes(expected)) {
    throw new Error(`export self-check missing ${expected}`);
  }
}

if (!ddl.includes('CREATE INDEX "idx_orders_user_id_cardinality"')) {
  throw new Error('export self-check missing applied index DDL');
}

const recommendations = buildIndexRecommendations({
  tableName: 'public.orders',
  rowCount: 10000,
  columns: [
    { columnName: 'user_id', isSelected: true, distinctCount: 9000 },
    { columnName: 'status', isSelected: true, distinctCount: 4 },
  ],
});

if (
  recommendations[0]?.index_name !== 'idx_orders_user_id_status' ||
  recommendations[0]?.strength !== 'recommended'
) {
  throw new Error('cardinality self-check did not recommend composite index');
}
