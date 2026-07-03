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

import { render, screen } from '@testing-library/react';
import { test, vi } from 'vitest';

vi.mock('@xyflow/react', async (importOriginal) => {
  const mod = await importOriginal<typeof import('@xyflow/react')>();
  return {
    ...mod,
    Handle: () => <div data-testid="handle" />,
    Position: { Top: 'top', Right: 'right', Bottom: 'bottom', Left: 'left' }
  };
});

test('renders TableNode with correct aria-labels for abbreviations', () => {
  const nodeProps = {
    id: 'test-node',
    data: {
      title: 'Users',
      columns: [
        { column_name: 'id', data_type: 'int', is_pk: true, is_not_null: true },
        { column_name: 'email', data_type: 'varchar', is_not_null: true }
      ],
      badges: {
        pk: true,
        fk: true
      }
    },
    type: 'tableNode' as const,
    selected: false,
    zIndex: 1,
    isConnectable: true,
    positionAbsoluteX: 0,
    positionAbsoluteY: 0,
    dragging: false,
    draggable: false,
    selectable: false,
    deletable: false,
  };

  render(<TableNode {...nodeProps} />);

  const pkBadges = screen.getAllByLabelText('Primary Key');
  expect(pkBadges.length).toBeGreaterThan(0);

  const fkBadges = screen.getAllByLabelText('Foreign Key');
  expect(fkBadges.length).toBeGreaterThan(0);

  const nnBadges = screen.getAllByLabelText('Not Null');
  expect(nnBadges.length).toBeGreaterThan(0);
});
