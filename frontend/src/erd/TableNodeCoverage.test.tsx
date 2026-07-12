import '@testing-library/jest-dom/vitest'
import { ReactFlowProvider } from '@xyflow/react'
import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import TableNode from './TableNode'

const baseColumns = Array.from({ length: 26 }, (_, index) => ({
  column_name: `column_${index}`,
  data_type: index === 0 ? 'bigint' : 'text',
  is_not_null: index === 0,
  is_pk: index === 0,
  column_comment: index === 0 ? '   ' : null,
  example_value: index === 0 ? 0 : index === 1 ? false : index === 2 ? '   ' : null,
}))

const baseData = {
  title: 'public.users',
  comment: '   ',
  columns: baseColumns,
  businessGroup: { id: 'g1', name: 'Core', color: '#ff0000' },
  indexes: Array.from({ length: 5 }, (_, index) => ({
    index_name: `idx_${index}`,
    columns: [`column_${index}`],
    access_method: 'btree',
  })),
  isDimmed: true,
  isHighlighted: true,
  badges: { pk: true, fk: true },
}

function element(data: any) {
  return (
    <ReactFlowProvider>
      <TableNode {...({ data, id: 'node', type: 'tableNode', isConnectable: true } as any)} />
    </ReactFlowProvider>
  )
}

afterEach(cleanup)

describe('TableNode rendering and memo coverage', () => {
  it('renders truncation, empty metadata, falsy examples, badges, and overflow summaries', () => {
    const { rerender } = render(element(baseData))
    expect(screen.getByLabelText('생략된 컬럼이 더 있습니다')).toHaveTextContent('1 more')
    expect(screen.getByLabelText('생략된 인덱스가 더 있습니다')).toHaveTextContent('1 more indexes')
    expect(screen.getByText('e.g. 0')).toBeInTheDocument()
    expect(screen.getByText('e.g. false')).toBeInTheDocument()
    expect(screen.queryByText('e.g.')).not.toBeInTheDocument()
    expect(screen.getAllByLabelText('Primary Key').length).toBeGreaterThan(1)
    expect(screen.getByRole('region')).toHaveClass('tableNode--grouped', 'tableNode--dimmed', 'tableNode--highlighted')

    rerender(
      element({
        title: 'ungrouped',
        columns: [{ column_name: 'id', data_type: 'int', is_not_null: false }],
      }),
    )
    expect(screen.getByRole('region')).not.toHaveClass('tableNode--grouped')
    expect(screen.queryByLabelText('추천 인덱스')).not.toBeInTheDocument()
  })

  it('exercises every rendered-field memo comparison and the 25-column boundary', () => {
    const { rerender } = render(element(baseData))
    rerender(element(baseData))
    rerender(element({ ...baseData, columns: baseColumns }))

    const same = () => ({
      ...baseData,
      columns: baseColumns.map((column) => ({ ...column })),
      businessGroup: { ...baseData.businessGroup },
    })
    const compare = (changed: Record<string, unknown>) => {
      rerender(element(same()))
      rerender(element({ ...same(), ...changed }))
    }

    compare({ title: 'other' })
    compare({ comment: 'other' })
    compare({ indexes: [...baseData.indexes] })
    compare({ businessGroup: { ...baseData.businessGroup, id: 'g2' } })
    compare({ businessGroup: { ...baseData.businessGroup, name: 'Other' } })
    compare({ businessGroup: { ...baseData.businessGroup, color: '#00ff00' } })
    compare({ isDimmed: false })
    compare({ isHighlighted: false })
    compare({ badges: { ...baseData.badges, pk: false } })
    compare({ badges: { ...baseData.badges, fk: false } })

    compare({ columns: baseColumns.slice(0, 25) })
    for (const [field, value] of [
      ['column_name', 'changed'],
      ['data_type', 'uuid'],
      ['is_not_null', false],
      ['is_pk', false],
      ['column_comment', 'changed'],
      ['example_value', 'changed'],
    ] as const) {
      const columns = baseColumns.map((column) => ({ ...column }))
      columns[0] = { ...columns[0]!, [field]: value }
      compare({ columns })
    }

    const hiddenChange = baseColumns.map((column) => ({ ...column }))
    hiddenChange[25] = { ...hiddenChange[25]!, data_type: 'uuid' }
    compare({ columns: hiddenChange })
    expect(screen.getByText('public.users')).toBeInTheDocument()
  })
})
