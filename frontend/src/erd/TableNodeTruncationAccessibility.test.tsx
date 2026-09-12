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
  it('keeps non-interactive omission summaries out of sequential keyboard focus', () => {
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
    const summaries = markup.match(/<div class="tableNode__more"[^>]*>/g) ?? []

    expect(summaries).toHaveLength(2)
    for (const summary of summaries) {
      expect(summary).not.toContain('tabindex=')
      expect(summary).not.toContain('role="button"')
    }
    expect(summaries[0]).toContain('aria-label="생략된 컬럼이 더 있습니다"')
    expect(markup).toContain('… 1 more')
    expect(summaries[1]).toContain('aria-label="생략된 인덱스가 더 있습니다"')
    expect(markup).toContain('… 1 more indexes')
  })
})
