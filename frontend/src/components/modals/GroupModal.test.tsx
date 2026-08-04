import '@testing-library/jest-dom/vitest';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import type { Node } from '@xyflow/react'
import type { TableNodeData } from '../../erd/convert'
import { GroupModal } from './GroupModal';

afterEach(() => {
  cleanup();
});

const tableNode: Node<TableNodeData> = {
  id: 'table-1',
  type: 'tableNode',
  position: { x: 10, y: 20 },
  data: {
    title: 'public.users',
    comment: '',
    columns: [],
    badges: { pk: true, fk: false },
  },
}

describe('GroupModal', () => {
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

    // Test prevent default on form submission where name is empty
    const form = screen.getByRole('dialog').querySelector('form')
    fireEvent.submit(form!)
    expect(onCreate).not.toHaveBeenCalled()

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

    // test form submission success
    fireEvent.submit(form!)
    expect(onCreate).toHaveBeenCalledOnce()

    // Cancel deletion
    vi.spyOn(window, 'confirm').mockReturnValueOnce(false)
    fireEvent.click(screen.getByRole('button', { name: 'Billing 그룹 삭제' }))
    expect(window.confirm).toHaveBeenCalledWith("'Billing' 그룹을 삭제하시겠습니까?")
    expect(onDelete).not.toHaveBeenCalled()

    // Proceed deletion
    vi.spyOn(window, 'confirm').mockReturnValueOnce(true)
    fireEvent.click(screen.getByRole('button', { name: 'Billing 그룹 삭제' }))
    expect(window.confirm).toHaveBeenCalledWith("'Billing' 그룹을 삭제하시겠습니까?")
    expect(onDelete).toHaveBeenCalledWith('g1')

    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'g1' } })
    expect(onAssign).toHaveBeenCalledWith('table-1', 'g1')

    fireEvent.click(screen.getByRole('button', { name: '업무 그룹 닫기' }))
    expect(setName).toHaveBeenCalledWith('New')
    expect(setColor).toHaveBeenCalled()
    expect(onClose).toHaveBeenCalledOnce()
  })
});
