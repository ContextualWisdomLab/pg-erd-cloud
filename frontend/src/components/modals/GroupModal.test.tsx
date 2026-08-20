import '@testing-library/jest-dom/vitest';
import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';

import { GroupModal } from './GroupModal';

describe('GroupModal', () => {
  it('exposes truncated assignment table names accessibly', () => {
    const tableName = 'analytics.extremely_long_customer_activity_table';

    render(
      <GroupModal
        isOpen
        businessGroups={[]}
        newGroupName=""
        setNewGroupName={vi.fn()}
        newGroupColor="#1f77b4"
        setNewGroupColor={vi.fn()}
        nodes={[
          {
            id: 'table-1',
            type: 'tableNode',
            position: { x: 0, y: 0 },
            data: {
              title: tableName,
              columns: [],
              badges: { pk: false, fk: false },
            },
          },
        ]}
        onCloseGroupManager={vi.fn()}
        onCreateBusinessGroup={vi.fn()}
        onDeleteBusinessGroup={vi.fn()}
        onAssignBusinessGroup={vi.fn()}
      />,
    );

    expect(screen.getByLabelText(/그룹 이름/)).toBeRequired();
    const tableLabel = screen
      .getAllByLabelText(tableName)
      .find((element) => element.tagName === 'SPAN');
    expect(tableLabel).toBeDefined();
    expect(tableLabel).toHaveAttribute('title', tableName);
    expect(tableLabel).not.toHaveAttribute('tabindex', '0');
  });

  it('does not delete a group when confirmation is canceled', () => {
    const onDeleteBusinessGroup = vi.fn();
    vi.spyOn(window, 'confirm').mockReturnValue(false);

    render(
      <GroupModal
        isOpen
        businessGroups={[{ id: 'g1', name: 'Billing', color: '#1f77b4' }]}
        newGroupName=""
        setNewGroupName={vi.fn()}
        newGroupColor="#1f77b4"
        setNewGroupColor={vi.fn()}
        nodes={[]}
        onCloseGroupManager={vi.fn()}
        onCreateBusinessGroup={vi.fn()}
        onDeleteBusinessGroup={onDeleteBusinessGroup}
        onAssignBusinessGroup={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Billing 그룹 삭제' }));
    expect(onDeleteBusinessGroup).not.toHaveBeenCalled();
  });
});
