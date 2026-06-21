import { ReactFlowProvider, type Edge, type Node } from '@xyflow/react';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';

import { buildIndexRecommendations } from './cardinality';
import { exportDDL, exportDiagramSvg, exportPlantUml } from './export';
import TableNode from './TableNode';
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
      businessGroup: { id: 'group_sales', name: 'Sales', color: '#2563eb' },
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

for (const expected of ['public.users', 'application users', 'public.orders [Sales]', 'fk_orders_user', 'idx_orders_user_id', 'gin:btree_gin', 'idx_orders_user_id_cardinality', 'user id', '1001']) {
  if (!uml.includes(expected) || !svg.includes(expected)) {
    throw new Error(`export self-check missing ${expected}`);
  }
}

if (!ddl.includes('CREATE INDEX CONCURRENTLY "idx_orders_user_id_cardinality"')) {
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

const hostileMarkupNodes: Array<Node<TableNodeData>> = [
  {
    id: 'hostile',
    type: 'tableNode',
    position: { x: 0, y: 0 },
    data: {
      title: 'public.hostile<script>alert(1)</script>',
      businessGroup: {
        id: 'group_hostile',
        name: 'Ops <script>alert(2)</script>',
        color: 'not-a-safe-svg-color',
      },
      columns: [
        {
          column_name: 'payload',
          data_type: 'text<script>alert(3)</script>',
          is_not_null: false,
          is_pk: false,
          column_comment: '<script>alert(4)</script>',
          example_value: '<script>alert(5)</script>',
        },
      ],
      badges: { pk: false, fk: false },
    },
  },
];
const hostileSvg = exportDiagramSvg(hostileMarkupNodes, []);

if (hostileSvg.includes('<script')) {
  throw new Error('export self-check emitted raw script markup');
}

const TableNodeForSelfcheck = TableNode as unknown as React.ComponentType<{
  data: TableNodeData;
}>;
const hostileTableNodeMarkup = renderToStaticMarkup(
  React.createElement(
    ReactFlowProvider,
    null,
    React.createElement(TableNodeForSelfcheck, {
      data: {
        title: 'public.hostile',
        comment: '<script>alert(4)</script>',
        columns: [
          {
            column_name: 'payload',
            data_type: 'text',
            is_not_null: false,
            is_pk: false,
            column_comment: '<img src=x onerror="alert(6)">',
            example_value: '<svg onload=alert(7)>',
          },
        ],
        badges: { pk: false, fk: false },
      },
    }),
  ),
);

if (
  hostileTableNodeMarkup.includes('<script') ||
  hostileTableNodeMarkup.includes('<img') ||
  hostileTableNodeMarkup.includes('<svg')
) {
  throw new Error('TableNode self-check emitted raw markup');
}

if (!hostileTableNodeMarkup.includes('&lt;script&gt;alert(4)&lt;/script&gt;')) {
  throw new Error('TableNode self-check did not render comments as escaped text');
}

if (hostileSvg.includes('not-a-safe-svg-color')) {
  throw new Error('export self-check emitted an untrusted group color');
}

if (!hostileSvg.includes('fill="#047857" fill-opacity="0.18"')) {
  throw new Error('export self-check did not normalize the group color');
}

const hostilePlantMarkup = exportPlantUml(hostileMarkupNodes, [], null);

if (hostilePlantMarkup.includes('<script')) {
  throw new Error('export self-check emitted raw PlantUML script syntax');
}

if (!hostilePlantMarkup.includes('&lt;script&gt;alert(1)&lt;/script&gt;')) {
  throw new Error('export self-check did not encode PlantUML markup');
}

const ddlInjectionNode: Node<TableNodeData> = {
  id: 'ddl_injection',
  type: 'tableNode',
  position: { x: 0, y: 0 },
  data: {
    title: 'malicious_table"; DROP TABLE important_data; --',
    columns: [
      {
        column_name: 'id"; DROP TABLE audit_log; --',
        data_type: 'integer); DROP TABLE type_injection; --',
        is_not_null: true,
        is_pk: true,
      },
    ],
    indexes: [
      {
        index_name: 'idx_bad"; DROP INDEX safe_index; --',
        columns: ['id"; DROP TABLE audit_log; --'],
        access_method: 'btree); DROP TABLE access_method; --' as never,
        estimated_distinct: 1,
        cardinality_ratio: 1,
        strength: 'recommended',
        reason: 'self-check',
        source: 'cardinality-wizard',
      },
    ],
    badges: { pk: true, fk: false },
  },
};
const hostileDdl = exportDDL([ddlInjectionNode], []);

if (!hostileDdl.includes('"malicious_table""; DROP TABLE important_data; --"')) {
  throw new Error('export self-check did not quote table identifiers');
}

if (hostileDdl.includes('malicious_table"; DROP TABLE')) {
  throw new Error('export self-check emitted an unescaped table identifier');
}

if (hostileDdl.includes('integer); DROP TABLE type_injection')) {
  throw new Error('export self-check emitted an unsafe data type');
}

if (hostileDdl.includes('USING btree); DROP TABLE')) {
  throw new Error('export self-check emitted an unsafe index access method');
}

const hostilePlantUml = exportPlantUml([ddlInjectionNode], [], null);

if (hostilePlantUml.includes('">')) {
  throw new Error('export self-check emitted raw PlantUML quote syntax');
}
