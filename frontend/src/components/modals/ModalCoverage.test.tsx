import '@testing-library/jest-dom/vitest'
import type { Node } from '@xyflow/react'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { TableNodeData } from '../../erd/convert'
import { AddTableModal } from './AddTableModal'
import { CardinalityModal } from './CardinalityModal'
import { EditEdgeModal } from './EditEdgeModal'
import { EditTableModal } from './EditTableModal'
import { GroupModal } from './GroupModal'

const tableNode: Node<TableNodeData> = {
  id: 'table-1',
  type: 'tableNode',
  position: { x: 10, y: 20 },
  data: {
    title: 'public.users',
    comment: '',
    columns: [
      {
        column_name: 'id',
        data_type: 'bigint',
        is_not_null: true,
        is_pk: true,
      },
      {
        column_name: 'email',
        data_type: 'text',
        is_not_null: false,
        is_pk: false,
      },
    ],
    badges: { pk: true, fk: false },
  },
}

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

describe('modal behavior coverage', () => {
  it('covers AddTableModal visibility, input, validation, cancel, and submit', () => {
    const setNewTableName = vi.fn()
    const onCancel = vi.fn()
    const onSubmit = vi.fn()
    const { rerender } = render(
      <AddTableModal
        isOpen={false}
        newTableName=""
        setNewTableName={setNewTableName}
        onAddTableCancel={onCancel}
        onAddTableSubmit={onSubmit}
      />,
    )
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()

    rerender(
      <AddTableModal
        isOpen
        newTableName=""
        setNewTableName={setNewTableName}
        onAddTableCancel={onCancel}
        onAddTableSubmit={onSubmit}
      />,
    )
    fireEvent.change(screen.getByLabelText('테이블 이름'), { target: { value: 'users' } })
    fireEvent.submit(screen.getByRole('dialog'))
    expect(setNewTableName).toHaveBeenCalledWith('users')
    expect(onSubmit).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole('button', { name: '테이블 추가 취소' }))
    expect(onCancel).toHaveBeenCalledOnce()

    rerender(
      <AddTableModal
        isOpen
        newTableName=" users "
        setNewTableName={setNewTableName}
        onAddTableCancel={onCancel}
        onAddTableSubmit={onSubmit}
      />,
    )
    fireEvent.submit(screen.getByRole('dialog'))
    expect(onSubmit).toHaveBeenCalledOnce()
    expect(screen.getByRole('button', { name: '저장' })).toBeEnabled()
  })

  it('covers EditEdgeModal visibility and actions', () => {
    const setRelLabel = vi.fn()
    const onDelete = vi.fn()
    const onCancel = vi.fn()
    const onSubmit = vi.fn()
    const { rerender } = render(
      <EditEdgeModal
        editingEdge={null}
        relLabel=""
        setRelLabel={setRelLabel}
        onRelDelete={onDelete}
        onRelCancel={onCancel}
        onRelSubmit={onSubmit}
      />,
    )
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    rerender(
      <EditEdgeModal
        editingEdge={{ id: 'e', source: 'a', target: 'b', label: '' }}
        relLabel="fk_users"
        setRelLabel={setRelLabel}
        onRelDelete={onDelete}
        onRelCancel={onCancel}
        onRelSubmit={onSubmit}
      />,
    )
    expect(screen.getByText(/From: a/)).toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('제약조건 이름 (Label)'), {
      target: { value: 'fk_changed' },
    })
    fireEvent.click(screen.getByRole('button', { name: '관계 삭제' }))
    fireEvent.click(screen.getByRole('button', { name: '관계 설정 취소' }))
    fireEvent.click(screen.getByRole('button', { name: '저장' }))
    expect(setRelLabel).toHaveBeenCalledWith('fk_changed')
    expect(onDelete).toHaveBeenCalledOnce()
    expect(onCancel).toHaveBeenCalledOnce()
    expect(onSubmit).toHaveBeenCalledOnce()
  })

  it('covers EditTableModal column mutation, duplication, form, and table actions', () => {
    vi.spyOn(Date, 'now').mockReturnValue(123)
    const setNodes = vi.fn()
    const setEditingNode = vi.fn()
    const onCancel = vi.fn()
    const onSubmit = vi.fn((event: React.FormEvent) => event.preventDefault())
    const onDeleteTable = vi.fn()
    const otherNode = { ...tableNode, id: 'other' }
    const { rerender } = render(
      <EditTableModal
        isOpen={false}
        editingNode={null}
        setEditingNode={setEditingNode}
        setNodes={setNodes}
        onEditTableCancel={onCancel}
        onEditTableSubmit={onSubmit}
        onDeleteTable={onDeleteTable}
      />,
    )
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()

    rerender(
      <EditTableModal
        isOpen
        editingNode={tableNode}
        setEditingNode={setEditingNode}
        setNodes={setNodes}
        onEditTableCancel={onCancel}
        onEditTableSubmit={onSubmit}
        onDeleteTable={onDeleteTable}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: '컬럼 추가' }))
    const addNodes = setNodes.mock.calls[0]?.[0] as (nodes: Node<TableNodeData>[]) => Node<TableNodeData>[]
    expect(addNodes([otherNode, tableNode])[1]?.data.columns.at(-1)?.column_name).toBe('new_col_123')
    const addEditing = setEditingNode.mock.calls[0]?.[0] as (
      node: Node<TableNodeData> | null,
    ) => Node<TableNodeData> | null
    expect(addEditing(null)).toBeNull()
    expect(addEditing(tableNode)?.data.columns.at(-1)?.column_name).toBe('new_col_123')

    vi.spyOn(window, 'confirm').mockReturnValueOnce(false).mockReturnValueOnce(true)
    const deleteEmail = screen.getByRole('button', { name: 'email 컬럼 삭제' })
    fireEvent.click(deleteEmail)
    expect(setNodes).toHaveBeenCalledTimes(1)
    fireEvent.click(deleteEmail)
    const deleteNodes = setNodes.mock.calls[1]?.[0] as (nodes: Node<TableNodeData>[]) => Node<TableNodeData>[]
    expect(deleteNodes([otherNode, tableNode])[1]?.data.columns).toHaveLength(1)
    const deleteEditing = setEditingNode.mock.calls[1]?.[0] as (
      node: Node<TableNodeData> | null,
    ) => Node<TableNodeData> | null
    expect(deleteEditing(null)).toBeNull()
    expect(deleteEditing(tableNode)?.data.columns).toHaveLength(1)

    fireEvent.submit(document.getElementById('editTableForm')!)
    fireEvent.click(screen.getByRole('button', { name: '테이블 삭제' }))
    fireEvent.click(screen.getByRole('button', { name: '테이블 복제' }))
    const duplicate = setNodes.mock.calls[2]?.[0] as (nodes: Node<TableNodeData>[]) => Node<TableNodeData>[]
    const duplicated = duplicate([tableNode])[1]!
    expect(duplicated).toMatchObject({
      id: 'table-1_copy_123',
      position: { x: 50, y: 60 },
      data: { title: 'public.users_copy' },
    })
    expect(duplicated.data.columns).not.toBe(tableNode.data.columns)
    fireEvent.click(screen.getByRole('button', { name: '테이블 편집 취소' }))
    fireEvent.click(screen.getByRole('button', { name: '닫기' }))
    expect(onSubmit).toHaveBeenCalledOnce()
    expect(onDeleteTable).toHaveBeenCalledOnce()
    expect(onCancel).toHaveBeenCalledTimes(3)
  })

  it('covers GroupModal creation, color, deletion, assignment, and empty/list states', () => {
    const setName = vi.fn()
    const setColor = vi.fn()
    const onClose = vi.fn()
    const onCreate = vi.fn()
    const onDelete = vi.fn()
    const onAssign = vi.fn()
    const group = { id: 'g1', name: 'Billing', color: '#1f77b4' }
    const groupedNode = {
      ...tableNode,
      data: { ...tableNode.data, businessGroup: group },
    }
    const { rerender } = render(
      <GroupModal
        isOpen={false}
        businessGroups={[]}
        newGroupName=""
        setNewGroupName={setName}
        newGroupColor="#1f77b4"
        setNewGroupColor={setColor}
        nodes={[]}
        onCloseGroupManager={onClose}
        onCreateBusinessGroup={onCreate}
        onDeleteBusinessGroup={onDelete}
        onAssignBusinessGroup={onAssign}
      />,
    )
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    rerender(
      <GroupModal
        isOpen
        businessGroups={[]}
        newGroupName=""
        setNewGroupName={setName}
        newGroupColor="#1f77b4"
        setNewGroupColor={setColor}
        nodes={[tableNode]}
        onCloseGroupManager={onClose}
        onCreateBusinessGroup={onCreate}
        onDeleteBusinessGroup={onDelete}
        onAssignBusinessGroup={onAssign}
      />,
    )
    expect(screen.getByText('등록된 그룹이 없습니다.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '추가' })).toBeDisabled()

    rerender(
      <GroupModal
        isOpen
        businessGroups={[group]}
        newGroupName=" Team "
        setNewGroupName={setName}
        newGroupColor="#1f77b4"
        setNewGroupColor={setColor}
        nodes={[groupedNode]}
        onCloseGroupManager={onClose}
        onCreateBusinessGroup={onCreate}
        onDeleteBusinessGroup={onDelete}
        onAssignBusinessGroup={onAssign}
      />,
    )
    fireEvent.change(screen.getByLabelText('그룹 이름'), { target: { value: 'New' } })
    fireEvent.click(screen.getAllByRole('button', { name: /^색상 / })[1]!)
    fireEvent.click(screen.getByRole('button', { name: '추가' }))
    fireEvent.click(screen.getByRole('button', { name: 'Billing 그룹 삭제' }))
    fireEvent.change(screen.getByRole('combobox'), { target: { value: '' } })
    fireEvent.click(screen.getByRole('button', { name: '업무 그룹 닫기' }))
    expect(setName).toHaveBeenCalledWith('New')
    expect(setColor).toHaveBeenCalled()
    expect(onCreate).toHaveBeenCalledOnce()
    expect(onDelete).toHaveBeenCalledWith('g1')
    expect(onAssign).toHaveBeenCalledWith('table-1', '')
    expect(onClose).toHaveBeenCalledOnce()
  })

  it('covers CardinalityModal validation, ratios, applied states, and callbacks', () => {
    const callbacks = {
      close: vi.fn(),
      table: vi.fn(),
      toggle: vi.fn(),
      distinct: vi.fn(),
      apply: vi.fn(),
      rows: vi.fn(),
    }
    const recommendation = {
      index_name: 'idx_users_email',
      columns: ['email'],
      access_method: 'btree' as const,
      estimated_distinct: 50,
      cardinality_ratio: 0.5,
      strength: 'recommended' as const,
      reason: 'selective',
      source: 'cardinality-wizard' as const,
    }
    const skipRecommendation = {
      ...recommendation,
      index_name: '',
      columns: ['id'],
      strength: 'skip' as const,
    }
    const common = {
      nodes: [tableNode],
      cardinalityRowCount: '100',
      setCardinalityRowCount: callbacks.rows,
      cardinalityDistinctCounts: { id: '', email: '50' },
      cardinalityColumnSelections: { email: true },
      onCloseCardinalityWizard: callbacks.close,
      onCardinalityTableChange: callbacks.table,
      onCardinalityColumnToggle: callbacks.toggle,
      onCardinalityDistinctCountChange: callbacks.distinct,
      onApplyCardinalityRecommendation: callbacks.apply,
      parsePositiveInteger: (value: string) => {
        const parsed = Number(value)
        return Number.isInteger(parsed) && parsed > 0 ? parsed : null
      },
      calculateCardinalityRatio: (rows: number, distinct: number) => distinct / rows,
      formatPercent: (value: number) => `${value * 100}%`,
      strengthLabel: (strength: string) => strength.toUpperCase(),
    }
    const { rerender } = render(
      <CardinalityModal
        {...common}
        isOpen={false}
        cardinalityNode={null}
        cardinalityRowCountNumber={null}
        cardinalityRecommendations={[]}
        appliedCardinalitySignatures={{ names: new Set(), columns: new Set() }}
      />,
    )
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()

    rerender(
      <CardinalityModal
        {...common}
        isOpen
        cardinalityNode={null}
        cardinalityRowCountNumber={null}
        cardinalityRecommendations={[]}
        appliedCardinalitySignatures={{ names: new Set(), columns: new Set() }}
      />,
    )
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()

    rerender(
      <CardinalityModal
        {...common}
        isOpen
        cardinalityNode={tableNode}
        cardinalityRowCountNumber={null}
        cardinalityRecommendations={[]}
        appliedCardinalitySignatures={{ names: new Set(), columns: new Set() }}
      />,
    )
    expect(screen.getByText('Rows 값을 입력하세요.')).toBeInTheDocument()
    expect(screen.getAllByText('—')).toHaveLength(2)

    rerender(
      <CardinalityModal
        {...common}
        cardinalityDistinctCounts={{}}
        cardinalityColumnSelections={{}}
        isOpen
        cardinalityNode={tableNode}
        cardinalityRowCountNumber={100}
        cardinalityRecommendations={[]}
        appliedCardinalitySignatures={{ names: new Set(), columns: new Set() }}
      />,
    )
    expect(screen.getByText('사용할 컬럼과 distinct 값을 선택하세요.')).toBeInTheDocument()

    rerender(
      <CardinalityModal
        {...common}
        isOpen
        cardinalityNode={tableNode}
        cardinalityRowCountNumber={100}
        cardinalityRecommendations={[recommendation, skipRecommendation]}
        appliedCardinalitySignatures={{
          names: new Set(['idx_users_email']),
          columns: new Set(['id']),
        }}
      />,
    )
    fireEvent.change(screen.getByLabelText('테이블'), { target: { value: 'table-1' } })
    fireEvent.change(screen.getByLabelText('행 수'), { target: { value: '200' } })
    fireEvent.change(screen.getByLabelText('email distinct count'), { target: { value: '75' } })
    fireEvent.click(screen.getByLabelText('email 사용'))
    expect(screen.getByText('50%')).toBeInTheDocument()
    expect(screen.getAllByRole('button', { name: '적용됨' })).toHaveLength(2)

    rerender(
      <CardinalityModal
        {...common}
        isOpen
        cardinalityNode={tableNode}
        cardinalityRowCountNumber={100}
        cardinalityRecommendations={[recommendation]}
        appliedCardinalitySignatures={{ names: new Set(), columns: new Set() }}
      />,
    )
    fireEvent.click(screen.getByRole('button', { name: '적용' }))
    fireEvent.click(screen.getByRole('button', { name: '카디널리티 계산 닫기' }))
    expect(callbacks.table).toHaveBeenCalledWith('table-1')
    expect(callbacks.rows).toHaveBeenCalledWith('200')
    expect(callbacks.distinct).toHaveBeenCalledWith('email', '75')
    expect(callbacks.toggle).toHaveBeenCalledWith('email', false)
    expect(callbacks.apply).toHaveBeenCalledWith(recommendation)
    expect(callbacks.close).toHaveBeenCalledOnce()
  })
})
