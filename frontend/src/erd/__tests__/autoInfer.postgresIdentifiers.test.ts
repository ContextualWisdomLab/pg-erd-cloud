import { describe, expect, it } from 'vitest'

import { inferRelationships } from '../autoInfer'
import { snapshotToGraph } from '../convert'

type SnapshotInput = Parameters<typeof snapshotToGraph>[0]

describe('inferRelationships PostgreSQL identifier fidelity', () => {
  it('preserves Unicode, spaces, and dots in PostgreSQL relation names', () => {
    const snapshot: SnapshotInput = {
      relations: [
        { relation_oid: 1, relation_kind: 'r', schema_name: 'public', relation_name: '사용자' },
        { relation_oid: 2, relation_kind: 'r', schema_name: 'public', relation_name: '활동' },
        { relation_oid: 3, relation_kind: 'r', schema_name: 'public', relation_name: 'Order Items' },
        { relation_oid: 4, relation_kind: 'r', schema_name: 'public', relation_name: 'Order Audit' },
        { relation_oid: 5, relation_kind: 'r', schema_name: 'public', relation_name: 'Order.Items' },
        { relation_oid: 6, relation_kind: 'r', schema_name: 'public', relation_name: 'Dotted Audit' },
      ],
      columns: [
        { relation_oid: 1, column_name: 'id', data_type: 'bigint', is_not_null: true },
        { relation_oid: 2, column_name: '사용자_id', data_type: 'bigint', is_not_null: true },
        { relation_oid: 3, column_name: 'id', data_type: 'bigint', is_not_null: true },
        { relation_oid: 4, column_name: 'Order Items_id', data_type: 'bigint', is_not_null: true },
        { relation_oid: 5, column_name: 'id', data_type: 'bigint', is_not_null: true },
        { relation_oid: 6, column_name: 'Order.Items_id', data_type: 'bigint', is_not_null: true },
      ],
      constraints: [],
    }

    const { nodes } = snapshotToGraph(snapshot)
    const edges = inferRelationships(nodes)

    expect(edges).toHaveLength(3)
    expect(edges).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ source: '2', target: '1' }),
        expect.objectContaining({ source: '4', target: '3' }),
        expect.objectContaining({ source: '6', target: '5' }),
      ]),
    )
  })
})
