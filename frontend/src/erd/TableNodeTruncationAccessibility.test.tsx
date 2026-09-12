import { ReactFlowProvider } from '@xyflow/react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import TableNode from './TableNode'
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
    const indexes = Array.from({ length: 5 }, (_, index) => ({
      index_name: `idx_${index + 1}`,
      columns: ['column_1'],
      access_method: 'btree'
    }))

    const markup = renderTableNode({
      title: 'orders',
      columns,
      indexes,
      badges: { pk: false, fk: false }
    })

    expect(markup).toContain(
      'tabindex="0" title="생략된 컬럼이 더 있습니다" aria-label="생략된 컬럼이 더 있습니다"'
    )
    expect(markup).toContain('… 1 more')
    expect(markup).toContain(
      'tabindex="0" title="생략된 인덱스가 더 있습니다" aria-label="생략된 인덱스가 더 있습니다"'
    )
    expect(markup).toContain('… 1 more indexes')
  })
})
