import '@testing-library/jest-dom/vitest';
import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';

import { GroupModal } from './GroupModal';

describe('GroupModal', () => {
  it('reports whitespace-only group names as invalid', () => {
    const onCreateBusinessGroup = vi.fn();

    render(
      <GroupModal
        isOpen
        businessGroups={[]}
        newGroupName="   "
        setNewGroupName={vi.fn()}
        newGroupColor="#1f77b4"
        setNewGroupColor={vi.fn()}
        nodes={[]}
        onCloseGroupManager={vi.fn()}
        onCreateBusinessGroup={onCreateBusinessGroup}
        onDeleteBusinessGroup={vi.fn()}
        onAssignBusinessGroup={vi.fn()}
      />,
    );

    const input = screen.getByLabelText(/그룹 이름/) as HTMLInputElement;
    const reportValidity = vi.spyOn(input, 'reportValidity');
    fireEvent.submit(input.closest('form')!);

    expect(input).toHaveAttribute('aria-invalid', 'true');
    expect(reportValidity).toHaveBeenCalledOnce();
    expect(onCreateBusinessGroup).not.toHaveBeenCalled();
  });

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

    const tableLabel = screen
      .getAllByLabelText(tableName)
      .find((element) => element.tagName === 'SPAN');
    expect(tableLabel).toBeDefined();
    expect(tableLabel).toHaveAttribute('title', tableName);
    expect(tableLabel).not.toHaveAttribute('tabindex', '0');
  });
});
