import { ReactFlowProvider } from '@xyflow/react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import TableNode from './TableNode'
import type { IndexRecommendation } from './cardinality'
import type { TableNodeData } from './convert'

const TableNodeForTest = TableNode as unknown as React.ComponentType<{
  data: TableNodeData
}>

function renderTableNode(data: TableNodeData): string {
  return renderToStaticMarkup(
    <ReactFlowProvider>
      <TableNodeForTest data={data} />
    </ReactFlowProvider>
  )
}

describe('TableNode truncated-population accessibility', () => {
  it('keeps omitted column and index summaries keyboard-focusable and explicitly named', () => {
    const columns = Array.from({ length: 26 }, (_, index) => ({
      column_name: `column_${index + 1}`,
      data_type: 'text',
      is_not_null: false,
      is_pk: false
    }))
    const indexes: IndexRecommendation[] = Array.from({ length: 5 }, (_, index) => ({
      index_name: `idx_${index + 1}`,
      columns: ['column_1'],
      access_method: 'btree',
      estimated_distinct: 100,
      cardinality_ratio: 0.5,
      strength: 'recommended',
      reason: 'focused accessibility fixture',
      source: 'cardinality-wizard'
    }))

    const markup = renderTableNode({
      title: 'orders',
      columns,
      indexes,
      badges: { pk: false, fk: false }
    })

    expect(markup).toContain(
      'aria-hidden="true"'
    )
    expect(markup).toContain('… 1 more')
    expect(markup).toContain(
      'aria-hidden="true"'
    )
    expect(markup).toContain('… 1 more indexes')
  })
})
