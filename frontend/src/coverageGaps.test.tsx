import '@testing-library/jest-dom/vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import type { Edge, Node } from '@xyflow/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { EditEdgeModal } from './components/modals/EditEdgeModal';
import { GroupModal } from './components/modals/GroupModal';
import type { BusinessGroup } from './erd/businessGroups';
import type { TableNodeData } from './erd/convert';
import { exportPrisma } from './erd/prisma';

afterEach(() => {
  vi.restoreAllMocks();
});

describe('remaining user-interaction branches', () => {
  it('keeps an edge when deletion is cancelled and deletes after confirmation', () => {
    const onRelDelete = vi.fn();
    const confirm = vi.spyOn(window, 'confirm').mockReturnValueOnce(false).mockReturnValueOnce(true);

    render(
      <EditEdgeModal
        editingEdge={{ id: 'edge-one', source: 'users', target: 'orders' }}
        relLabel="users_orders"
        setRelLabel={vi.fn()}
        onRelDelete={onRelDelete}
        onRelCancel={vi.fn()}
        onRelSubmit={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: '삭제' }));
    expect(onRelDelete).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: '삭제' }));
    expect(onRelDelete).toHaveBeenCalledTimes(1);
    expect(confirm).toHaveBeenCalledTimes(2);
  });

  it('guards blank group creation and cancelled deletion before allowing valid actions', () => {
    const groups: BusinessGroup[] = [{ id: 'billing-group', name: 'Billing', color: '#034ea2' }];
    const nodes: Node<TableNodeData>[] = [
      {
        id: 'users-table',
        position: { x: 0, y: 0 },
        data: { title: 'users', columns: [], badges: { pk: false, fk: false } },
      },
    ];
    const onCreateBusinessGroup = vi.fn();
    const onDeleteBusinessGroup = vi.fn();
    const confirm = vi.spyOn(window, 'confirm').mockReturnValueOnce(false).mockReturnValueOnce(true);
    const { rerender } = render(
      <GroupModal
        isOpen
        businessGroups={groups}
        newGroupName="   "
        setNewGroupName={vi.fn()}
        newGroupColor="#034ea2"
        setNewGroupColor={vi.fn()}
        nodes={nodes}
        onCloseGroupManager={vi.fn()}
        onCreateBusinessGroup={onCreateBusinessGroup}
        onDeleteBusinessGroup={onDeleteBusinessGroup}
        onAssignBusinessGroup={vi.fn()}
      />,
    );

    fireEvent.submit(screen.getByRole('button', { name: '추가' }).closest('form')!);
    expect(onCreateBusinessGroup).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: 'Billing 그룹 삭제' }));
    expect(onDeleteBusinessGroup).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: 'Billing 그룹 삭제' }));
    expect(onDeleteBusinessGroup).toHaveBeenCalledWith('billing-group');

    rerender(
      <GroupModal
        isOpen
        businessGroups={groups}
        newGroupName="Analytics"
        setNewGroupName={vi.fn()}
        newGroupColor="#034ea2"
        setNewGroupColor={vi.fn()}
        nodes={nodes}
        onCloseGroupManager={vi.fn()}
        onCreateBusinessGroup={onCreateBusinessGroup}
        onDeleteBusinessGroup={onDeleteBusinessGroup}
        onAssignBusinessGroup={vi.fn()}
      />,
    );
    fireEvent.submit(screen.getByRole('button', { name: '추가' }).closest('form')!);
    expect(onCreateBusinessGroup).toHaveBeenCalledTimes(1);
    expect(confirm).toHaveBeenCalledTimes(2);
  });
});

describe('remaining Prisma export branches', () => {
  const nodes: Node<TableNodeData>[] = [
    {
      id: 'users',
      position: { x: 0, y: 0 },
      data: {
        title: 'users',
        badges: { pk: true, fk: false },
        columns: [{ column_name: 'id', data_type: 'serial', is_pk: true, is_not_null: true }],
      },
    },
    {
      id: 'profiles',
      position: { x: 100, y: 0 },
      data: {
        title: 'profiles',
        badges: { pk: true, fk: true },
        columns: [{ column_name: 'id', data_type: 'integer', is_pk: true, is_not_null: true }],
      },
    },
  ];

  it('ignores an edge whose target node is absent', () => {
    const edges: Edge[] = [{ id: 'missing-target', source: 'profiles', target: 'absent' }];
    expect(exportPrisma(nodes, edges)).toContain('model profiles');
  });

  it('emits an optional singular back-relation for a unique source field', () => {
    const edges: Edge[] = [
      {
        id: 'unique-relation',
        source: 'profiles',
        target: 'users',
        sourceHandle: 'src-id',
        targetHandle: 'tgt-id',
        label: 'profile_owner',
      },
    ];
    expect(exportPrisma(nodes, edges)).toContain(
      'profiles_id profiles? @relation("profile_owner")',
    );
  });
});
