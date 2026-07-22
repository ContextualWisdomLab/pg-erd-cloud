import '@testing-library/jest-dom/vitest';
import { describe, expect, it, vi } from 'vitest';
import { render, screen, fireEvent, cleanup } from '@testing-library/react';
import { afterEach } from 'vitest';

import { GroupModal } from './GroupModal';

describe('GroupModal', () => {
  afterEach(cleanup);

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

  it('does not call onCreateBusinessGroup if newGroupName is empty on form submit', () => {
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
      />
    );

    const form = screen.getByRole('dialog').querySelector('form');
    expect(form).not.toBeNull();
    fireEvent.submit(form!);
    expect(onCreateBusinessGroup).not.toHaveBeenCalled();
  });

  it('calls onCreateBusinessGroup if newGroupName is valid on form submit', () => {
    const onCreateBusinessGroup = vi.fn();

    render(
      <GroupModal
        isOpen
        businessGroups={[]}
        newGroupName="New Group"
        setNewGroupName={vi.fn()}
        newGroupColor="#1f77b4"
        setNewGroupColor={vi.fn()}
        nodes={[]}
        onCloseGroupManager={vi.fn()}
        onCreateBusinessGroup={onCreateBusinessGroup}
        onDeleteBusinessGroup={vi.fn()}
        onAssignBusinessGroup={vi.fn()}
      />
    );

    const form = screen.getByRole('dialog').querySelector('form');
    expect(form).not.toBeNull();
    fireEvent.submit(form!);
    expect(onCreateBusinessGroup).toHaveBeenCalled();
  });
});
