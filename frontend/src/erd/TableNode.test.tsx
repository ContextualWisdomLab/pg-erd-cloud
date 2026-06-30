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

describe('TableNode', () => {
  it('escapes user supplied table and column text', () => {
    const markup = renderTableNode({
      title: '<script>alert("title")</script>',
      comment: '<script>alert("comment")</script>',
      columns: [
        {
          column_name: '<img src=x onerror=alert(1)>',
          data_type: 'text',
          is_not_null: false,
          is_pk: false,
          column_comment: '<script>alert("column")</script>',
          example_value: '<script>alert("example")</script>'
        }
      ],
      badges: { pk: false, fk: false }
    })

    expect(markup).not.toContain('<script>')
    expect(markup).not.toContain('<img src=x onerror=alert(1)>')
    expect(markup).toContain('&lt;script&gt;alert(&quot;comment&quot;)&lt;/script&gt;')
    expect(markup).toContain('&lt;img src=x onerror=alert(1)&gt;')
  })
})
